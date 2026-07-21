"""Model Lab endpoints (US-14, SPEC §12.4): run the leaderboard over the gold
set, read past runs, and adopt a winner — which is a logged config change."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.db import org_scoped_session
from app.core.roles import Role, require_role
from app.core.tenancy import require_org_id
from app.models import AuditLog, ModelLabRun
from app.services import modellab

router = APIRouter()

VALID_ROLES = {"extraction", "verdicts", "writing"}


class RunIn(BaseModel):
    role: str = "extraction"


class AdoptIn(BaseModel):
    gateway_role: str            # small | mid | strong
    model: str = Field(min_length=1)
    reason: str = Field(min_length=5)
    actor: str = Field(min_length=2)


class LabRunOut(BaseModel):
    id: uuid.UUID
    role: str
    gold_tenders: int
    leaderboard: list
    simulated: bool
    created_at: datetime


@router.post("/modellab/run")
async def run(
    body: RunIn | None = None,
    org_id: uuid.UUID = Depends(require_org_id),
    _role: Role = Depends(require_role(Role.ADMIN)),
) -> dict:
    role = (body.role if body else "extraction")
    return await modellab.run_and_store(org_id, role if role in VALID_ROLES else "extraction")


@router.get("/modellab/runs", response_model=list[LabRunOut])
async def runs(
    org_id: uuid.UUID = Depends(require_org_id),
    _role: Role = Depends(require_role(Role.ADMIN, Role.AUDITOR)),
) -> list[LabRunOut]:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(ModelLabRun).order_by(ModelLabRun.created_at.desc()).limit(20)
            )
        ).scalars()
        return [
            LabRunOut(id=r.id, role=r.role, gold_tenders=r.gold_tenders,
                      leaderboard=r.leaderboard, simulated=r.simulated,
                      created_at=r.created_at)
            for r in rows
        ]


@router.post("/modellab/adopt")
async def adopt(
    body: AdoptIn,
    org_id: uuid.UUID = Depends(require_org_id),
    _role: Role = Depends(require_role(Role.ADMIN)),
) -> dict:
    """Adopt a model as the winner for a gateway role. This is a CONFIG change
    (an env update + restart) — here it is recorded, with its evidence, in the
    append-only audit log."""
    async with org_scoped_session(org_id) as session:
        session.add(AuditLog(
            org_id=org_id, actor=body.actor, action="model_adopted",
            details={"gateway_role": body.gateway_role, "model": body.model,
                     "reason": body.reason},
        ))
    return {"adopted": body.model, "gateway_role": body.gateway_role,
            "note": "recorded as a config event — update .env and restart the "
                    "gateway to take effect"}
