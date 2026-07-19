"""Tenders: manual upload (US-03), parse status, and the grounded elements
feed that click-to-proof (US-04) will draw its highlight boxes from."""

import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import Document, Element, Page, ParseRun, Tender
from app.observability import get_parse_logger
from app.parsing import get_ladder
from app.services import extraction as extraction_service
from app.services import ingest
from app.services import triage as triage_service
from app.storage import ObjectStorage

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

    try:
        ingest.validate_pdf_upload(data, settings.max_upload_mb * 1024 * 1024)
    except ingest.UploadValidationError as error:
        raise HTTPException(error.status_code, error.detail)

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
    background.add_task(triage_service.triage_after_parse, org_id, tender_id)
    background.add_task(extraction_service.extract_after_parse, org_id, tender_id)
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
                select(Document).where(Document.tender_id == tender_id)
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
                select(Document).where(Document.tender_id == tender_id)
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
            )
            for e in elements
        ]
