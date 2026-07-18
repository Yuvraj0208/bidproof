import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.routers import discovery, health, tenders

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if get_settings().scout_enabled:
        from app.services.scheduler import discovery_loop

        task = asyncio.create_task(discovery_loop())
        logger.info("discovery scheduler started")
    yield
    if task is not None:
        task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="BidProof API", version="0.1.0", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(tenders.router)
    app.include_router(discovery.router)
    return app


app = create_app()
