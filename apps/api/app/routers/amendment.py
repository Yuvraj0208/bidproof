"""Amendment Watcher endpoints (US-07): apply a corrigendum and read the
alerts. The alert names exactly what changed, which rules broke, and the
new EV."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import Amendment
from app.services import amendments, ingest
from app.services.checking import get_checking_gateway
from app.storage import ObjectStorage

router = APIRouter()


class AmendmentOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    message: str
    changes: list
    rules_affected: list
    rules_broken: list
    ev_before_inr: float | None
    ev_after_inr: float | None
    created_at: str


@router.post("/tenders/{tender_id}/amend")
async def amend(
    tender_id: uuid.UUID,
    file: UploadFile = File(...),
    org_id: uuid.UUID = Depends(require_org_id),
    gateway=Depends(get_checking_gateway),
) -> dict:
    data = await file.read()
    settings = get_settings()
    try:
        ingest.validate_pdf_upload(data, settings.max_upload_mb * 1024 * 1024)
    except ingest.UploadValidationError as error:
        raise HTTPException(error.status_code, error.detail)

    try:
        result = await amendments.apply_amendment(
            org_id, tender_id, data, ObjectStorage(settings),
            filename=file.filename or "corrigendum.pdf", gateway=gateway,
        )
    except ingest.DuplicateDocumentError:
        raise HTTPException(409, "this corrigendum was already applied")
    if result is None:
        raise HTTPException(404, "tender not found")
    return result


@router.get("/tenders/{tender_id}/amendments", response_model=list[AmendmentOut])
async def list_amendments(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> list[AmendmentOut]:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(Amendment)
                .where(Amendment.tender_id == tender_id)
                .order_by(Amendment.created_at.desc())
            )
        ).scalars()
        return [
            AmendmentOut(
                id=a.id, document_id=a.document_id, message=a.message,
                changes=a.changes, rules_affected=a.rules_affected,
                rules_broken=a.rules_broken,
                ev_before_inr=float(a.ev_before_inr) if a.ev_before_inr is not None else None,
                ev_after_inr=float(a.ev_after_inr) if a.ev_after_inr is not None else None,
                created_at=a.created_at.isoformat(),
            )
            for a in rows
        ]
