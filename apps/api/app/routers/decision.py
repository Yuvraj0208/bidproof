"""Decision Room endpoints (US-06): compute the EV, read the Bid Brief,
sign off (Checkpoint 4 — a named human, never automatic), override with a
written reason. Everything lands in the append-only audit log."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import Decision, RiskRow, Tender, VerdictRow
from app.services import deciding

router = APIRouter()


class DecideIn(BaseModel):
    tender_value_inr: float | None = Field(default=None, gt=0)


class SignOffIn(BaseModel):
    name: str = Field(min_length=2)


class OverrideIn(BaseModel):
    name: str = Field(min_length=2)
    recommendation: str
    reason: str = Field(min_length=5)


@router.post("/tenders/{tender_id}/decide")
async def compute(
    tender_id: uuid.UUID,
    body: DecideIn | None = None,
    org_id: uuid.UUID = Depends(require_org_id),
) -> dict:
    result = await deciding.compute_decision(
        org_id, tender_id,
        tender_value_inr=body.tender_value_inr if body else None,
    )
    if result is None:
        raise HTTPException(404, "tender not found")
    return result


@router.get("/tenders/{tender_id}/brief")
async def bid_brief(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> dict:
    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            raise HTTPException(404, "tender not found")
        decision = (
            await session.execute(
                select(Decision).where(Decision.tender_id == tender_id)
            )
        ).scalar_one_or_none()
        risks = (
            await session.execute(
                select(RiskRow).where(RiskRow.tender_id == tender_id)
            )
        ).scalars().all()
        verdict_rows = (
            await session.execute(
                select(VerdictRow.verdict).where(VerdictRow.tender_id == tender_id)
            )
        ).scalars().all()

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    top_risks = sorted(
        risks, key=lambda r: (severity_rank.get(r.severity, 3),
                              -(float(r.rupee_impact) if r.rupee_impact else 0)),
    )[:5]
    counts: dict[str, int] = {}
    for verdict in verdict_rows:
        counts[verdict] = counts.get(verdict, 0) + 1

    return {
        "tender": {"id": str(tender.id), "title": tender.title,
                   "closing_at": tender.closing_at.isoformat() if tender.closing_at else None},
        "decision": deciding._decision_dict(decision) if decision else None,
        "verdict_counts": counts,
        "top_risks": [
            {"code": r.code, "severity": r.severity, "message": r.message,
             "rupee_impact": float(r.rupee_impact) if r.rupee_impact else None}
            for r in top_risks
        ],
    }


@router.post("/tenders/{tender_id}/decision/signoff")
async def sign_off(
    tender_id: uuid.UUID,
    body: SignOffIn,
    org_id: uuid.UUID = Depends(require_org_id),
) -> dict:
    result = await deciding.sign_off(org_id, tender_id, body.name.strip())
    if result is None:
        raise HTTPException(404, "no decision to sign off — run /decide first")
    return result


@router.post("/tenders/{tender_id}/decision/override")
async def override(
    tender_id: uuid.UUID,
    body: OverrideIn,
    org_id: uuid.UUID = Depends(require_org_id),
) -> dict:
    if body.recommendation not in ("go", "no_go"):
        raise HTTPException(400, "recommendation must be go or no_go")
    result = await deciding.override(
        org_id, tender_id, body.name.strip(), body.recommendation,
        body.reason.strip(),
    )
    if result is None:
        raise HTTPException(404, "no decision to override — run /decide first")
    return result
