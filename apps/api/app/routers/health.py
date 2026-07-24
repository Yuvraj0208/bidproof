import asyncio

from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import get_engine
from app.llm import availability

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    db_status = "ok"
    try:
        async with asyncio.timeout(2):
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"
    return {"status": "ok", "db": db_status}


@router.get("/health/models")
async def model_health(refresh: bool = False) -> dict:
    """Which model roles are actually reachable, and therefore whether results
    come from real models or the deterministic fallback. The UI shows this so a
    template answer is never mistaken for a model answer (FINISH_STATUS D9)."""
    status = availability.cached()
    if refresh or status is None:
        status = await availability.refresh()
    return status
