"""Manual upload -> the shared parse pipeline (US-03, SPEC §5.1).

Every input path (upload now; Scout and AmendmentWatcher later) funnels into
`execute_parse_run`, so there is exactly one pipeline to guard and test.
"""

import asyncio
import hashlib
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.models import Document, Element, Page, ParseRun, Tender
from app.observability import ParseRunLog, record_agent_run
from app.storage import ObjectStorage
from bidproof_parser import ParserLadder, compute_parse_cost_inr

PDF_MAGIC = b"%PDF-"


class UploadValidationError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class DuplicateDocumentError(Exception):
    def __init__(self, tender_id: uuid.UUID) -> None:
        super().__init__("document already uploaded")
        self.tender_id = tender_id


def validate_pdf_upload(data: bytes, max_bytes: int) -> None:
    """Input guardrails (SPEC §10): type by magic bytes, bounded size.
    The file is attacker-controlled input (§11.1) — trust nothing about it."""
    if not data or not data.startswith(PDF_MAGIC):
        raise UploadValidationError(415, "only PDF files are accepted")
    if len(data) > max_bytes:
        raise UploadValidationError(
            413, f"file exceeds the {max_bytes // (1024 * 1024)} MB upload limit"
        )


async def create_tender_with_document(
    org_id: uuid.UUID,
    *,
    filename: str,
    title: str,
    data: bytes,
    storage: ObjectStorage,
    source: str = "manual",
    external_id: str | None = None,
    portal_url: str | None = None,
    closing_at=None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str]:
    """Store the raw file and create tender + document + pending parse run.
    Shared by manual upload and the Scout — every input path funnels here.
    Returns (tender_id, document_id, parse_run_id, object_key)."""
    sha = hashlib.sha256(data).hexdigest()

    async with org_scoped_session(org_id) as session:
        existing = await session.execute(
            select(Document.tender_id).where(Document.sha256 == sha)
        )
        row = existing.first()
        if row:
            raise DuplicateDocumentError(row[0])

        object_key = f"{org_id}/{sha}.pdf"
        await asyncio.to_thread(storage.put_pdf, object_key, data)

        tender = Tender(
            org_id=org_id,
            title=title,
            source=source,
            external_id=external_id,
            portal_url=portal_url,
            closing_at=closing_at,
        )
        session.add(tender)
        await session.flush()

        document = Document(
            org_id=org_id,
            tender_id=tender.id,
            filename=filename,
            sha256=sha,
            size_bytes=len(data),
            bucket=storage.bucket,
            object_key=object_key,
        )
        session.add(document)
        await session.flush()

        run = ParseRun(
            org_id=org_id,
            document_id=document.id,
            status="pending",
            trace_id=tender.id.hex,
        )
        session.add(run)
        await session.flush()

        return tender.id, document.id, run.id, object_key


async def add_document_to_tender(
    org_id: uuid.UUID,
    tender_id: uuid.UUID,
    *,
    filename: str,
    data: bytes,
    storage: ObjectStorage,
    kind: str = "corrigendum",
) -> tuple[uuid.UUID, uuid.UUID]:
    """Attach a new document version (a corrigendum) to an existing tender.
    Returns (document_id, parse_run_id). Dedup by sha256 still applies."""
    from sqlalchemy import func as sql_func

    sha = hashlib.sha256(data).hexdigest()
    async with org_scoped_session(org_id) as session:
        existing = await session.execute(
            select(Document.id).where(Document.sha256 == sha)
        )
        if existing.first():
            raise DuplicateDocumentError(tender_id)

        next_version = (
            await session.execute(
                select(sql_func.coalesce(sql_func.max(Document.version), 0) + 1)
                .where(Document.tender_id == tender_id)
            )
        ).scalar_one()

        object_key = f"{org_id}/{sha}.pdf"
        await asyncio.to_thread(storage.put_pdf, object_key, data)

        document = Document(
            org_id=org_id, tender_id=tender_id, filename=filename, sha256=sha,
            size_bytes=len(data), bucket=storage.bucket, object_key=object_key,
            version=next_version, kind=kind,
        )
        session.add(document)
        await session.flush()

        run = ParseRun(org_id=org_id, document_id=document.id, status="pending",
                       trace_id=tender_id.hex)
        session.add(run)
        await session.flush()
        return document.id, run.id


async def create_upload_records(
    org_id: uuid.UUID,
    filename: str,
    title: str | None,
    data: bytes,
    storage: ObjectStorage,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str]:
    return await create_tender_with_document(
        org_id,
        filename=filename,
        title=title or filename,
        data=data,
        storage=storage,
        source="manual",
    )


async def execute_parse_run(
    org_id: uuid.UUID,
    tender_id: uuid.UUID,
    document_id: uuid.UUID,
    parse_run_id: uuid.UUID,
    pdf_bytes: bytes,
    ladder: ParserLadder,
    parse_logger,
) -> None:
    settings = get_settings()
    started = time.monotonic()

    async with org_scoped_session(org_id) as session:
        run = await session.get(ParseRun, parse_run_id)
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)

    try:
        result = await asyncio.to_thread(ladder.parse, pdf_bytes)
    except Exception as exc:
        async with org_scoped_session(org_id) as session:
            run = await session.get(ParseRun, parse_run_id)
            run.status = "failed"
            run.error = str(exc)[:2000]
            run.finished_at = datetime.now(timezone.utc)
        parse_logger.log(
            ParseRunLog(
                trace_id=tender_id.hex,
                tender_id=str(tender_id),
                document_id=str(document_id),
                parse_run_id=str(parse_run_id),
                status="failed",
                pages_total=0,
                pages_text=0,
                pages_ocr=0,
                pages_flagged=0,
                elements=0,
                elements_discarded=0,
                cost_inr=0.0,
                duration_s=round(time.monotonic() - started, 3),
                error=str(exc)[:500],
            )
        )
        await record_agent_run(
            org_id, tender_id, "parser", status="failed",
            duration_ms=int((time.monotonic() - started) * 1000),
            meta={"error": str(exc)[:300]},
        )
        return

    # Rupee cost is plain arithmetic — never a model (§9 rule 2).
    cost_inr = compute_parse_cost_inr(result.pages_ocr, settings.ocr_cost_per_page_inr)
    status = "needs_human" if result.needs_human else "succeeded"
    element_count = 0

    async with org_scoped_session(org_id) as session:
        for page in result.pages:
            session.add(
                Page(
                    org_id=org_id,
                    document_id=document_id,
                    page_no=page.page_no,
                    width=page.width,
                    height=page.height,
                    route=page.route.value,
                    status=page.status.value,
                    confidence=page.confidence,
                )
            )
        await session.flush()

        for page in result.pages:
            for element in page.elements:
                element_count += 1
                session.add(
                    Element(
                        org_id=org_id,
                        document_id=document_id,
                        page_no=element.page_no,
                        kind=element.kind,
                        text=element.text,
                        x0=element.bbox.x0,
                        y0=element.bbox.y0,
                        x1=element.bbox.x1,
                        y1=element.bbox.y1,
                        confidence=element.confidence,
                        seq=element.seq,
                    )
                )

        document = await session.get(Document, document_id)
        document.page_count = result.pages_total

        run = await session.get(ParseRun, parse_run_id)
        run.status = status
        run.pages_total = result.pages_total
        run.pages_text = result.pages_text
        run.pages_ocr = result.pages_ocr
        run.pages_flagged = result.pages_flagged
        run.elements_discarded = result.elements_discarded
        run.cost_inr = cost_inr
        run.finished_at = datetime.now(timezone.utc)

    parse_logger.log(
        ParseRunLog(
            trace_id=tender_id.hex,
            tender_id=str(tender_id),
            document_id=str(document_id),
            parse_run_id=str(parse_run_id),
            status=status,
            pages_total=result.pages_total,
            pages_text=result.pages_text,
            pages_ocr=result.pages_ocr,
            pages_flagged=result.pages_flagged,
            elements=element_count,
            elements_discarded=result.elements_discarded,
            cost_inr=cost_inr,
            duration_s=round(time.monotonic() - started, 3),
        )
    )
    await record_agent_run(
        org_id, tender_id, "parser",
        duration_ms=int((time.monotonic() - started) * 1000),
        cost_inr=cost_inr,
        meta={"pages_total": result.pages_total, "pages_ocr": result.pages_ocr,
              "pages_flagged": result.pages_flagged, "elements": element_count},
    )
