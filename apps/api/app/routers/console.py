"""Agent Console endpoints (US-12, SPEC §13): every agent call under the
tender's trace id, the totals line that is the whole business case, and
replay."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import AgentRun
from app.services import replay

router = APIRouter()


class AgentRunOut(BaseModel):
    id: uuid.UUID
    trace_id: str
    agent: str
    status: str
    model_role: str | None
    prompt_version: str | None
    tokens_in: int
    tokens_out: int
    cost_inr: float
    duration_ms: int
    meta: dict
    created_at: str


@router.get("/tenders/{tender_id}/agent-runs")
async def agent_runs(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> dict:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(AgentRun)
                .where(AgentRun.tender_id == tender_id)
                .order_by(AgentRun.created_at)
            )
        ).scalars().all()

    runs = [
        AgentRunOut(
            id=r.id, trace_id=r.trace_id, agent=r.agent, status=r.status,
            model_role=r.model_role, prompt_version=r.prompt_version,
            tokens_in=r.tokens_in, tokens_out=r.tokens_out,
            cost_inr=float(r.cost_inr), duration_ms=r.duration_ms,
            meta=r.meta, created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
    return {
        "runs": [run.model_dump(mode="json") for run in runs],
        "totals": {
            "calls": len(runs),
            "tokens": sum(r.tokens_in + r.tokens_out for r in runs),
            "cost_inr": round(sum(r.cost_inr for r in runs), 4),
            "duration_ms": sum(r.duration_ms for r in runs),
        },
    }


@router.post("/tenders/{tender_id}/replay")
async def replay_run(
    tender_id: uuid.UUID, org_id: uuid.UUID = Depends(require_org_id)
) -> dict:
    result = await replay.replay_tender(org_id, tender_id)
    if result is None:
        raise HTTPException(404, "tender has no stored document to replay")
    return result
