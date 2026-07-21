"""Admin + audit endpoints (US-16, SPEC §14).

The audit log is append-only and readable by the auditor (or admin). Model
swaps are logged config events — the model is pinned; a swap records who
changed it, to what, and why, in the same append-only log.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.db import org_scoped_session
from app.core.roles import Role, require_role
from app.core.tenancy import require_org_id
from app.models import AuditLog

router = APIRouter()

PINNED_ROLES = ("small", "mid", "strong")


class AuditOut(BaseModel):
    id: uuid.UUID
    actor: str
    action: str
    tender_id: uuid.UUID | None
    details: dict
    created_at: datetime


class ModelSwapIn(BaseModel):
    role: str
    to_model: str = Field(min_length=1)
    reason: str = Field(min_length=5)
    actor: str = Field(min_length=2)


@router.get("/audit", response_model=list[AuditOut])
async def read_audit_log(
    limit: int = 100,
    org_id: uuid.UUID = Depends(require_org_id),
    _role: Role = Depends(require_role(Role.AUDITOR, Role.ADMIN)),
) -> list[AuditOut]:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500))
            )
        ).scalars()
        return [
            AuditOut(
                id=r.id, actor=r.actor, action=r.action, tender_id=r.tender_id,
                details=r.details, created_at=r.created_at,
            )
            for r in rows
        ]


@router.get("/admin/models")
async def pinned_models(
    org_id: uuid.UUID = Depends(require_org_id),
    _role: Role = Depends(require_role(Role.ADMIN)),
) -> dict:
    return {
        "roles": list(PINNED_ROLES),
        "note": "models are pinned via env config (never hardcoded in app "
                "code); a swap is a logged config event",
    }


@router.post("/admin/model-swap")
async def log_model_swap(
    body: ModelSwapIn,
    org_id: uuid.UUID = Depends(require_org_id),
    _role: Role = Depends(require_role(Role.ADMIN)),
) -> dict:
    """Record a model swap as an append-only audit event (SPEC §14). This does
    not itself change the running config — that is an env change + restart —
    it records the decision, who made it, and why."""
    if body.role not in PINNED_ROLES:
        raise HTTPException(400, f"role must be one of {PINNED_ROLES}")
    async with org_scoped_session(org_id) as session:
        session.add(AuditLog(
            org_id=org_id, actor=body.actor, action="model_swapped",
            details={"role": body.role, "to_model": body.to_model,
                     "reason": body.reason},
        ))
    return {"logged": True, "role": body.role, "to_model": body.to_model}
