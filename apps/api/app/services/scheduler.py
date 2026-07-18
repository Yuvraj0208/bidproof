"""The discovery scheduler: a periodic in-process loop (interval from env,
default 60 min — comfortably inside the 4-hour AC). Hand-off to Celery
workers is parked until workload demands it (parking-lot.md)."""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from bidproof_adapters import GuardedFetcher

from app.core.config import get_settings
from app.observability import get_parse_logger
from app.parsing import get_ladder
from app.services.discovery import build_allowlist, get_adapters, run_discovery
from app.storage import ObjectStorage

logger = logging.getLogger(__name__)


async def _org_ids() -> list:
    """Org enumeration is a system action: RLS hides organizations from the
    app role by design, so the scheduler lists org ids with the owner engine
    (read-only) and then does all real work through RLS-scoped sessions."""
    engine = create_async_engine(get_settings().database_url_owner)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(text("SELECT id FROM organizations"))
            return [row.id for row in rows]
    finally:
        await engine.dispose()


async def run_discovery_for_all_orgs() -> None:
    settings = get_settings()
    for org_id in await _org_ids():
        fetcher = GuardedFetcher(
            build_allowlist(),
            max_download_bytes=settings.max_upload_mb * 1024 * 1024,
        )
        try:
            report = await run_discovery(
                org_id=org_id,
                adapters=get_adapters(),
                fetcher=fetcher,
                storage=ObjectStorage(settings),
                ladder=get_ladder(),
                parse_logger=get_parse_logger(),
            )
            logger.info("discovery for org %s: %s", org_id, report)
        except Exception:
            logger.exception("discovery failed for org %s", org_id)
        finally:
            await fetcher.aclose()


async def discovery_loop() -> None:
    interval = get_settings().scout_interval_minutes * 60
    while True:
        await run_discovery_for_all_orgs()
        await asyncio.sleep(interval)
