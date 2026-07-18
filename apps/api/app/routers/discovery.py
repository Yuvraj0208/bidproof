"""Discovery endpoints: run the Scout now, and read past runs (the raw
data behind the Admin screen's scraper-health panel)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.core.tenancy import require_org_id
from app.models import DiscoveryRun
from app.observability import get_parse_logger
from app.parsing import get_ladder
from app.services.discovery import get_adapters, get_discovery_fetcher, run_discovery
from app.storage import ObjectStorage

router = APIRouter()


class DiscoveryRunOut(BaseModel):
    id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    report: dict


@router.post("/discovery/run")
async def trigger_discovery(
    org_id: uuid.UUID = Depends(require_org_id),
    adapters=Depends(get_adapters),
    fetcher=Depends(get_discovery_fetcher),
    ladder=Depends(get_ladder),
    parse_logger=Depends(get_parse_logger),
) -> dict:
    return await run_discovery(
        org_id=org_id,
        adapters=adapters,
        fetcher=fetcher,
        storage=ObjectStorage(get_settings()),
        ladder=ladder,
        parse_logger=parse_logger,
    )


@router.get("/discovery/runs", response_model=list[DiscoveryRunOut])
async def list_discovery_runs(
    org_id: uuid.UUID = Depends(require_org_id), limit: int = 20
) -> list[DiscoveryRunOut]:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(DiscoveryRun)
                .order_by(DiscoveryRun.started_at.desc())
                .limit(min(limit, 100))
            )
        ).scalars()
        return [
            DiscoveryRunOut(
                id=r.id,
                started_at=r.started_at,
                finished_at=r.finished_at,
                report=r.report,
            )
            for r in rows
        ]
