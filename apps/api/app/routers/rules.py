"""Rules endpoints (US-04): extraction trigger, the grounded rules feed
(each row joined to its element's page+box — the click-to-proof payload),
and the raw PDF stream the viewer renders."""

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import Document, Element, Rule
from app.services import extraction
from app.storage import ObjectStorage

router = APIRouter()


class BBoxOut(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class RuleOut(BaseModel):
    rule_id: uuid.UUID
    family: str
    key: str
    requirement_text: str
    value: str | None
    el_id: uuid.UUID
    page_no: int
    bbox: BBoxOut
    source: str
    status: str
    confidence: float
    band: str
    reason: str


@router.post("/tenders/{tender_id}/extract")
async def run_extraction(
    tender_id: uuid.UUID,
    org_id: uuid.UUID = Depends(require_org_id),
    gateway=Depends(extraction.get_extraction_gateway),
) -> dict:
    summary = await extraction.extract_rules(org_id, tender_id, gateway=gateway)
    if summary is None:
        raise HTTPException(404, "tender has no parsed document")
    return summary


@router.get("/tenders/{tender_id}/rules", response_model=list[RuleOut])
async def list_rules(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> list[RuleOut]:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(Rule, Element)
                .join(Element, Rule.el_id == Element.el_id)
                .where(Rule.tender_id == tender_id)
                .order_by(Rule.family, Rule.key)
            )
        ).all()
        return [
            RuleOut(
                rule_id=rule.rule_id,
                family=rule.family,
                key=rule.key,
                requirement_text=rule.requirement_text,
                value=rule.value_text,
                el_id=rule.el_id,
                page_no=element.page_no,
                bbox=BBoxOut(x0=element.x0, y0=element.y0, x1=element.x1, y1=element.y1),
                source=rule.source,
                status=rule.status,
                confidence=rule.confidence,
                band=rule.band,
                reason=rule.reason,
            )
            for rule, element in rows
        ]


@router.get("/tenders/{tender_id}/document")
async def get_document(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> Response:
    async with org_scoped_session(org_id) as session:
        document = (
            await session.execute(
                select(Document).where(Document.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        if document is None:
            raise HTTPException(404, "tender has no document")
        object_key = document.object_key

    storage = ObjectStorage(get_settings())
    data = await asyncio.to_thread(storage.get_pdf, object_key)
    return Response(content=data, media_type="application/pdf")
