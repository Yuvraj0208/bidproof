"""Tenders: manual upload (US-03), parse status, and the grounded elements
feed that click-to-proof (US-04) will draw its highlight boxes from."""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.services import portal_links
from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.core.roles import Role, require_role
from app.core.tenancy import require_known_org, require_org_id
from app.models import AuditLog, Document, Element, Page, ParseRun, Tender
from app.observability import get_parse_logger
from app.parsing import get_ladder
from app.services import checking as checking_service
from app.services import extraction as extraction_service
from app.services import ingest
from app.services import triage as triage_service
from app.storage import ObjectStorage

logger = logging.getLogger(__name__)

router = APIRouter()


class UploadOut(BaseModel):
    tender_id: uuid.UUID
    document_id: uuid.UUID
    parse_run_id: uuid.UUID
    object_key: str
    status: str


class ParseSummary(BaseModel):
    status: str
    pages_total: int | None
    pages_text: int | None
    pages_ocr: int | None
    pages_flagged: int | None
    elements_discarded: int | None
    cost_inr: float
    error: str | None


class PageOut(BaseModel):
    page_no: int
    route: str
    status: str
    confidence: float


class TenderDetailOut(BaseModel):
    id: uuid.UUID
    title: str
    source: str
    created_at: datetime
    parse: ParseSummary | None
    pages: list[PageOut]
    # A scraped portal listing has metadata but no PDF — the document sits
    # behind a portal session. Say so, rather than showing empty panels.
    has_document: bool = False
    portal_url: str | None = None
    portal_search_url: str | None = None
    portal_requires_captcha: bool = False
    portal_hint: str | None = None
    can_fetch_document: bool = False


class BBoxOut(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class ElementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    el_id: uuid.UUID
    page_no: int
    kind: str
    text: str
    bbox: BBoxOut
    confidence: float
    seq: int
    guard_flagged: bool = False
    guard_category: str | None = None


class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source: str
    created_at: datetime


@router.get("/tenders", response_model=list[TenderOut])
async def list_tenders(org_id: uuid.UUID = Depends(require_org_id)) -> list[TenderOut]:
    async with org_scoped_session(org_id) as session:
        result = await session.execute(
            select(Tender).order_by(Tender.created_at.desc())
        )
        return [TenderOut.model_validate(t) for t in result.scalars()]


@router.post("/tenders/upload", response_model=UploadOut, status_code=201)
async def upload_tender(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    org_id: uuid.UUID = Depends(require_org_id),
    ladder=Depends(get_ladder),
    parse_logger=Depends(get_parse_logger),
) -> UploadOut:
    settings = get_settings()
    data = await file.read()

    # The file check first: it is pure, needs no database, and "this is not a
    # PDF" is a more specific answer than anything about tenancy.
    try:
        ingest.validate_pdf_upload(data, settings.max_upload_mb * 1024 * 1024)
    except ingest.UploadValidationError as error:
        raise HTTPException(error.status_code, error.detail)

    # Then the tenant, before anything is written. A stale org id used to reach
    # the insert and die on a foreign key; the resulting 500 carries no CORS
    # header, so the browser showed only "TypeError: Failed to fetch".
    await require_known_org(org_id)

    try:
        tender_id, document_id, parse_run_id, object_key = (
            await ingest.create_upload_records(
                org_id=org_id,
                filename=file.filename or "upload.pdf",
                title=title,
                data=data,
                storage=ObjectStorage(settings),
            )
        )
    except ingest.DuplicateDocumentError as error:
        raise HTTPException(
            409, f"this document was already uploaded (tender {error.tender_id})"
        )

    background.add_task(
        ingest.execute_parse_run,
        org_id=org_id,
        tender_id=tender_id,
        document_id=document_id,
        parse_run_id=parse_run_id,
        pdf_bytes=data,
        ladder=ladder,
        parse_logger=parse_logger,
    )
    # Parsing and triage are free: local PDF reading and plain-code scoring.
    # Rule extraction and checking CALL MODELS and cost money, so they do NOT
    # run automatically — a human presses "Process with AI" on the tender they
    # actually care about (FINISH_STATUS R2). Nothing reaches a model unasked.
    background.add_task(triage_service.triage_after_parse, org_id, tender_id)
    return UploadOut(
        tender_id=tender_id,
        document_id=document_id,
        parse_run_id=parse_run_id,
        object_key=object_key,
        status="pending",
    )


@router.get("/tenders/{tender_id}", response_model=TenderDetailOut)
async def get_tender(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> TenderDetailOut:
    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            raise HTTPException(404, "tender not found")

        document = (
            await session.execute(
                select(Document)
                .where(Document.tender_id == tender_id)
                .order_by(Document.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        parse: ParseSummary | None = None
        pages: list[PageOut] = []
        if document is not None:
            run = (
                await session.execute(
                    select(ParseRun)
                    .where(ParseRun.document_id == document.id)
                    .order_by(ParseRun.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if run is not None:
                parse = ParseSummary(
                    status=run.status,
                    pages_total=run.pages_total,
                    pages_text=run.pages_text,
                    pages_ocr=run.pages_ocr,
                    pages_flagged=run.pages_flagged,
                    elements_discarded=run.elements_discarded,
                    cost_inr=float(run.cost_inr),
                    error=run.error,
                )
            page_rows = (
                await session.execute(
                    select(Page)
                    .where(Page.document_id == document.id)
                    .order_by(Page.page_no)
                )
            ).scalars()
            pages = [
                PageOut(
                    page_no=p.page_no,
                    route=p.route,
                    status=p.status,
                    confidence=p.confidence,
                )
                for p in page_rows
            ]

        return TenderDetailOut(
            id=tender.id,
            title=tender.title,
            source=tender.source,
            created_at=tender.created_at,
            parse=parse,
            pages=pages,
            has_document=document is not None,
            portal_url=portal_links.stable_portal_url(
                tender.source, tender.portal_url
            ),
            portal_search_url=portal_links.portal_search_url(tender.source),
            portal_requires_captcha=portal_links.requires_captcha(tender.source),
            portal_hint=portal_links.portal_hint(
                tender.source, tender.external_id, tender.portal_url
            ),
            can_fetch_document=(
                document is None
                and portal_links.document_url(tender.source, tender.portal_url)
                is not None
            ),
        )


@router.get("/tenders/{tender_id}/elements", response_model=list[ElementOut])
async def list_elements(
    tender_id: uuid.UUID,
    page_no: int | None = None,
    org_id: uuid.UUID = Depends(require_org_id),
) -> list[ElementOut]:
    async with org_scoped_session(org_id) as session:
        document = (
            await session.execute(
                select(Document)
                .where(Document.tender_id == tender_id)
                .order_by(Document.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if document is None:
            raise HTTPException(404, "tender has no document")

        query = (
            select(Element)
            .where(Element.document_id == document.id)
            .order_by(Element.page_no, Element.seq)
        )
        if page_no is not None:
            query = query.where(Element.page_no == page_no)

        elements = (await session.execute(query)).scalars()
        return [
            ElementOut(
                el_id=e.el_id,
                page_no=e.page_no,
                kind=e.kind,
                text=e.text,
                bbox=BBoxOut(x0=e.x0, y0=e.y0, x1=e.x1, y1=e.y1),
                confidence=e.confidence,
                seq=e.seq,
                guard_flagged=e.guard_flagged,
                guard_category=e.guard_category,
            )
            for e in elements
        ]


class ProcessOut(BaseModel):
    tender_id: uuid.UUID
    rules: int
    verdicts: dict
    model_calls: int
    # Which orchestration ran: "conductor" (the graph) or "sequential".
    # Surfaced so a demo can never claim the graph ran when it did not.
    orchestrator: str = "sequential"
    # The checkpoint the run stopped at, when the graph ran it.
    paused_at: int | None = None


@router.post("/tenders/{tender_id}/process", response_model=ProcessOut)
async def process_tender(
    tender_id: uuid.UUID,
    org_id: uuid.UUID = Depends(require_org_id),
    role: Role = Depends(require_role(Role.BID_EXECUTIVE)),
    gateway=Depends(extraction_service.get_extraction_gateway),
) -> ProcessOut:
    """The ONLY route by which a tender reaches a model (FINISH_STATUS R2).

    Upload and portal discovery deliberately stop after parsing and triage,
    which are free. Extraction and checking cost money, so a named human opts
    this specific tender in. The act is written to the append-only audit log so
    the spend is attributable.
    """
    async with org_scoped_session(org_id) as session:
        if await session.get(Tender, tender_id) is None:
            raise HTTPException(404, "tender not found")

    summary = await extraction_service.extract_rules(org_id, tender_id, gateway=gateway)
    if summary is None:
        raise HTTPException(
            409,
            "this tender has no parsed document yet — portal-discovered tenders "
            "often carry metadata only; upload the PDF to read it",
        )
    checked = await _run_checking(org_id, tender_id, gateway)

    async with org_scoped_session(org_id) as session:
        session.add(AuditLog(
            org_id=org_id, tender_id=tender_id, actor=role.value,
            action="tender_processed_with_ai",
            details={"rules": summary.get("rules", 0),
                     "model_calls": checked.get("model_calls", 0),
                     "orchestrator": checked.get("orchestrator", "sequential")},
        ))

    return ProcessOut(
        tender_id=tender_id,
        rules=summary.get("rules", 0),
        verdicts=checked.get("verdicts", {}),
        model_calls=checked.get("model_calls", 0),
        orchestrator=checked.get("orchestrator", "sequential"),
        paused_at=checked.get("paused_at"),
    )


async def _run_checking(org_id: uuid.UUID, tender_id: uuid.UUID, gateway) -> dict:
    """Check the tender, through the Conductor when it is available.

    Both routes execute the same service functions — the graph runs the Matcher
    and the RiskScorer concurrently and stops at checkpoint 4, the sequential
    path runs them in order. So this is an orchestration choice, and falling
    back to the sequential path is a real fallback rather than a degraded
    result.

    The fallback is deliberate and not silent: if the graph raises, checking
    still happens and the audit log records which route ran.
    """
    from app.conductor import conductor_available

    if get_settings().conductor_enabled and conductor_available():
        from app.conductor import run_tender

        try:
            # The request's gateway, so a stubbed one reaches the graph exactly
            # as it reaches the sequential path.
            run = await run_tender(org_id, tender_id, gateway=gateway)
            return {
                "verdicts": run["verdict_counts"],
                "model_calls": run["model_calls"],
                "orchestrator": "conductor",
                "paused_at": run["paused_at"],
            }
        except Exception:
            logger.exception(
                "the conductor failed for tender %s; falling back to the "
                "sequential path so checking still completes",
                tender_id,
            )

    # The same gateway serves both halves: the role is chosen per call inside
    # each service. Omitting it here does not fail — `_judge` short-circuits to
    # "no judge available" and every prose rule silently becomes needs_human.
    checked = await checking_service.run_checks(
        org_id, tender_id, gateway=gateway
    ) or {}
    return {**checked, "orchestrator": "sequential"}


@router.delete("/tenders/{tender_id}", status_code=200)
async def delete_tender(
    tender_id: uuid.UUID,
    org_id: uuid.UUID = Depends(require_org_id),
    role: Role = Depends(require_role(Role.BID_HEAD)),
) -> dict:
    """Remove a tender and everything derived from it (FINISH_STATUS R1).

    Portal discovery brings in a lot of noise, and a human needs to be able to
    clear it. Deletion is irreversible, so it is gated to bid_head-or-above and
    recorded in the append-only audit log FIRST — the audit row survives the
    cascade because it only references the tender id, not a foreign key.

    No agent can reach this: it is a human-only endpoint (repo golden rule 8).
    """
    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            raise HTTPException(404, "tender not found")
        title, source = tender.title, tender.source
        session.add(AuditLog(
            org_id=org_id, tender_id=tender_id, actor=role.value,
            action="tender_deleted",
            details={"title": title, "source": source},
        ))

    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is not None:
            await session.delete(tender)

    return {"deleted": str(tender_id), "title": title}


class BulkDeleteIn(BaseModel):
    tender_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class BulkDeleteOut(BaseModel):
    deleted: list[uuid.UUID]
    not_found: list[uuid.UUID]


@router.post("/tenders/bulk-delete", response_model=BulkDeleteOut)
async def bulk_delete_tenders(
    body: BulkDeleteIn,
    org_id: uuid.UUID = Depends(require_org_id),
    role: Role = Depends(require_role(Role.BID_HEAD)),
) -> BulkDeleteOut:
    """Clear a whole selection of tenders in one action.

    Portal discovery brings in far more noise than anyone wants to dismiss one
    row at a time. The guarantees of the single delete all still hold per
    tender: an audit row is written BEFORE the cascade, ids outside the caller's
    org are simply never found (RLS scopes the session), and no agent can reach
    this — it is human-only (repo golden rule 8).

    Ids that do not exist are reported back rather than failing the batch, so a
    stale tab cannot make the whole action fail.
    """
    # De-duplicate while keeping the caller's order, so the audit log reads the
    # way the human actually selected.
    wanted = list(dict.fromkeys(body.tender_ids))

    deleted: list[uuid.UUID] = []
    not_found: list[uuid.UUID] = []

    async with org_scoped_session(org_id) as session:
        for tender_id in wanted:
            tender = await session.get(Tender, tender_id)
            if tender is None:
                not_found.append(tender_id)
                continue
            session.add(AuditLog(
                org_id=org_id, tender_id=tender_id, actor=role.value,
                action="tender_deleted",
                details={"title": tender.title, "source": tender.source,
                         "batch": len(wanted)},
            ))
            deleted.append(tender_id)

    # Second transaction, so every audit row is committed before anything goes.
    async with org_scoped_session(org_id) as session:
        for tender_id in deleted:
            tender = await session.get(Tender, tender_id)
            if tender is not None:
                await session.delete(tender)

    return BulkDeleteOut(deleted=deleted, not_found=not_found)


class FetchDocumentOut(BaseModel):
    tender_id: uuid.UUID
    document_id: uuid.UUID
    pages: int
    status: str


@router.post("/tenders/{tender_id}/fetch-document", response_model=FetchDocumentOut)
async def fetch_portal_document(
    tender_id: uuid.UUID,
    org_id: uuid.UUID = Depends(require_org_id),
    role: Role = Depends(require_role(Role.BID_EXECUTIVE)),
    ladder=Depends(get_ladder),
    parse_logger=Depends(get_parse_logger),
) -> FetchDocumentOut:
    """Pull a portal-hosted tender document and read it.

    Only GeM qualifies today: it serves `/showbidDocument/<id>` as a plain PDF
    with no session, cookie or captcha. CPPP routes its documents through a POST
    form instead, so there is nothing here to fetch — `portal_links.document_url`
    is the gate, and it says no.

    Human-triggered on purpose. Discovery deliberately stops at metadata, so
    nobody wakes up to a few hundred megabytes of speculatively downloaded PDFs;
    a person asks for the tender they actually care about, and the act is
    audited.
    """
    from bidproof_adapters import GuardedFetcher

    from app.services import discovery as discovery_service

    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            raise HTTPException(404, "tender not found")
        source, portal_url, external_id = (
            tender.source, tender.portal_url, tender.external_id,
        )

    url = portal_links.document_url(source, portal_url)
    if url is None:
        raise HTTPException(
            409,
            f"{source.upper()} does not publish a directly fetchable document for "
            "this tender — download it from the portal and upload the PDF here",
        )

    settings = get_settings()
    fetcher = GuardedFetcher(discovery_service.build_allowlist())
    try:
        data = await fetcher.download(url)
    except Exception as exc:
        raise HTTPException(502, f"could not fetch the document: {exc}")
    finally:
        await fetcher.aclose()

    try:
        ingest.validate_pdf_upload(data, settings.max_upload_mb * 1024 * 1024)
    except ingest.UploadValidationError as error:
        # The portal answered with something that is not a usable PDF. Say so
        # rather than storing it and failing later.
        raise HTTPException(502, f"the portal did not return a usable PDF: {error.detail}")

    try:
        document_id, parse_run_id = await ingest.add_document_to_tender(
            org_id,
            tender_id,
            filename=f"{(external_id or str(tender_id)).replace('/', '_')}.pdf",
            data=data,
            storage=ObjectStorage(settings),
            # This is the tender's own document, not a corrigendum — the schema
            # allows 'original' | 'corrigendum' (migration 0010).
            kind="original",
        )
    except ingest.DuplicateDocumentError:
        raise HTTPException(409, "this document is already attached")

    await ingest.execute_parse_run(
        org_id=org_id,
        tender_id=tender_id,
        document_id=document_id,
        parse_run_id=parse_run_id,
        pdf_bytes=data,
        ladder=ladder,
        parse_logger=parse_logger,
    )
    await triage_service.triage_after_parse(org_id, tender_id)

    async with org_scoped_session(org_id) as session:
        run = await session.get(ParseRun, parse_run_id)
        pages, status = (run.pages_total or 0), run.status
        session.add(AuditLog(
            org_id=org_id, tender_id=tender_id, actor=role.value,
            action="portal_document_fetched",
            details={"url": url, "pages": pages, "bytes": len(data)},
        ))

    return FetchDocumentOut(
        tender_id=tender_id, document_id=document_id, pages=pages, status=status,
    )
