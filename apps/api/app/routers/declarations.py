"""Declaration endpoints (SPEC §5.8): the standard forms, filled from real
company data only — unfilled fields are left blank and flagged for a human."""

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.core.tenancy import require_org_id
from app.services import formfiller

router = APIRouter()


@router.get("/declarations")
async def list_declarations(
    org_id: uuid.UUID = Depends(require_org_id),
) -> list[dict]:
    return await formfiller.fill_all(org_id)


@router.get("/declarations/{template_id}")
async def get_declaration(
    template_id: str, org_id: uuid.UUID = Depends(require_org_id)
) -> dict:
    result = await formfiller.fill_one(org_id, template_id)
    if result is None:
        raise HTTPException(404, f"unknown declaration template {template_id!r}")
    return result
