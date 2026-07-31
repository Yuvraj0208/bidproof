"""Evaluation endpoints (the Evaluation screen).

Running an evaluator is a deliberate act — some load ML models and read every
gold PDF — so nothing here runs on a page load. The screen asks for what it
wants, and the slow ones are opt-in.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.tenancy import require_org_id
from app.services import evaluation

router = APIRouter()


@router.get("/evaluation/catalogue")
async def catalogue() -> dict:
    """What can be measured, without measuring anything."""
    return {"components": evaluation.catalogue()}


@router.post("/evaluation/run")
async def run(
    component: str | None = Query(default=None),
    include_slow: bool = Query(default=False),
    org_id: uuid.UUID = Depends(require_org_id),
) -> dict:
    """Run one evaluator, or every fast one. `include_slow` adds OCR and the
    text-engine comparison, which load models and take minutes."""
    if component:
        if component not in evaluation.BY_COMPONENT:
            raise HTTPException(
                404,
                f"unknown component {component!r}; known: "
                f"{sorted(evaluation.BY_COMPONENT)}",
            )
        results = [await evaluation.run_one(component, org_id)]
    else:
        results = await evaluation.run_all(org_id, include_slow=include_slow)
    return {"results": [r.to_dict() for r in results]}
