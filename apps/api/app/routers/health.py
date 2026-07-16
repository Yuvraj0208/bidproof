import asyncio

from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import get_engine

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
