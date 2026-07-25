"""Analytics endpoints (SPEC §17 screen 8). Read-only; every figure comes from
the same tables the pipeline writes, so the demo and the report agree."""

import uuid

from fastapi import APIRouter, Depends

from app.core.roles import Role, require_role
from app.core.tenancy import require_org_id
from app.services import analytics

router = APIRouter()


@router.get("/analytics/overview")
async def overview(
    days: int = 30,
    org_id: uuid.UUID = Depends(require_org_id),
    _role: Role = Depends(require_role(Role.VIEWER, Role.AUDITOR)),
) -> dict:
    return await analytics.overview(org_id, days=min(max(days, 1), 365))
