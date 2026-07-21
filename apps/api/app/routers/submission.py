"""Submission checklist endpoints (US-18, Checkpoint 6). The system checks
each document's format and signature; a human ticks each; nothing is
submit-ready until every required item is ticked."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.tenancy import require_org_id
from app.services import submission

router = APIRouter()


class AttachIn(BaseModel):
    format: str = Field(min_length=1)
    signed: bool = False


class TickIn(BaseModel):
    name: str = Field(min_length=2)


@router.post("/tenders/{tender_id}/checklist")
async def generate(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> dict:
    result = await submission.generate_checklist(org_id, tender_id)
    if result is None:
        raise HTTPException(404, "tender not found")
    return result


@router.get("/tenders/{tender_id}/checklist")
async def read(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> dict:
    result = await submission.read_checklist(org_id, tender_id)
    if result is None:
        raise HTTPException(404, "tender not found")
    return result


@router.post("/checklist/items/{item_id}/attach")
async def attach(
    item_id: uuid.UUID,
    body: AttachIn,
    org_id: uuid.UUID = Depends(require_org_id),
) -> dict:
    result = await submission.attach_file(org_id, item_id, body.format, body.signed)
    if result is None:
        raise HTTPException(404, "checklist item not found")
    return result


@router.post("/checklist/items/{item_id}/tick")
async def tick(
    item_id: uuid.UUID,
    body: TickIn,
    org_id: uuid.UUID = Depends(require_org_id),
) -> dict:
    result, error = await submission.tick_item(org_id, item_id, body.name.strip())
    if error is not None:
        raise HTTPException(409, error)
    if result is None:
        raise HTTPException(404, "checklist item not found")
    return result
