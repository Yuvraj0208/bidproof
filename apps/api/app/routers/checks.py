"""Checking endpoints (SPEC §5.5): run the Matcher + RiskScorer, read
verdicts (joined to their rule + element for click-to-proof) and risks."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import Element, RiskRow, Rule, VerdictRow
from app.services import checking

router = APIRouter()


class BBoxOut(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class VerdictOut(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    family: str
    key: str
    requirement_text: str
    value: str | None
    verdict: str
    reason: str
    confidence: float
    band: str
    arithmetic: bool
    cited_fact_id: uuid.UUID | None
    cited_product_id: uuid.UUID | None
    el_id: uuid.UUID
    page_no: int
    bbox: BBoxOut


class RiskOut(BaseModel):
    id: uuid.UUID
    code: str
    severity: str
    message: str
    rupee_impact: float | None
    el_id: uuid.UUID | None


@router.post("/tenders/{tender_id}/check")
async def run_check(
    tender_id: uuid.UUID,
    org_id: uuid.UUID = Depends(require_org_id),
    gateway=Depends(checking.get_checking_gateway),
) -> dict:
    summary = await checking.run_checks(org_id, tender_id, gateway=gateway)
    if summary is None:
        raise HTTPException(404, "tender not found")
    return summary


@router.get("/tenders/{tender_id}/verdicts", response_model=list[VerdictOut])
async def list_verdicts(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> list[VerdictOut]:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(VerdictRow, Rule, Element)
                .join(Rule, VerdictRow.rule_id == Rule.rule_id)
                .join(Element, Rule.el_id == Element.el_id)
                .where(VerdictRow.tender_id == tender_id)
                .order_by(Rule.family, Rule.key)
            )
        ).all()
        return [
            VerdictOut(
                id=v.id, rule_id=v.rule_id, family=r.family, key=r.key,
                requirement_text=r.requirement_text, value=r.value_text,
                verdict=v.verdict, reason=v.reason, confidence=v.confidence,
                band=v.band, arithmetic=v.arithmetic,
                cited_fact_id=v.cited_fact_id, cited_product_id=v.cited_product_id,
                el_id=e.el_id, page_no=e.page_no,
                bbox=BBoxOut(x0=e.x0, y0=e.y0, x1=e.x1, y1=e.y1),
            )
            for v, r, e in rows
        ]


@router.get("/tenders/{tender_id}/risks", response_model=list[RiskOut])
async def list_risks(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> list[RiskOut]:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(RiskRow)
                .where(RiskRow.tender_id == tender_id)
                .order_by(RiskRow.severity.desc(), RiskRow.code)
            )
        ).scalars()
        return [
            RiskOut(
                id=r.id, code=r.code, severity=r.severity, message=r.message,
                rupee_impact=float(r.rupee_impact) if r.rupee_impact is not None else None,
                el_id=r.el_id,
            )
            for r in rows
        ]
