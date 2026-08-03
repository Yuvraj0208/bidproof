import asyncio

from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import get_engine
from app.llm import availability

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Overall status must FOLLOW the database.

    This used to answer `{"status": "ok", "db": "unreachable"}` — a 200 that made
    the app look alive while every screen 500'd on a dead Postgres. The UI reads
    `status`, so a degraded database has to say degraded (FINISH_STATUS R0)."""
    db_status = "ok"
    detail = None
    try:
        async with asyncio.timeout(2):
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = "unreachable"
        detail = (
            "the database is not answering — start or restart the Postgres "
            f"container, then retry ({type(exc).__name__})"
        )
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "db": db_status,
        "detail": detail,
    }


@router.get("/health/models")
async def model_health(refresh: bool = False) -> dict:
    """Which model roles are actually reachable, and therefore whether results
    come from real models or the deterministic fallback. The UI shows this so a
    template answer is never mistaken for a model answer (FINISH_STATUS D9)."""
    status = availability.cached()
    if refresh or status is None:
        # `refresh` is the operator's explicit re-check; a stale cache is just
        # the badge's 60s poll, and those coalesce onto a single probe.
        status = await availability.refresh(force=refresh)
    return status
