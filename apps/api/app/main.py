import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import (
    admin,
    amendment,
    analytics,
    capability,
    chat,
    checks,
    console,
    declarations,
    decision,
    discovery,
    health,
    modellab,
    onboarding,
    proposal,
    questions,
    radar,
    rules,
    submission,
    tenders,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if get_settings().scout_enabled:
        from app.services.scheduler import discovery_loop

        task = asyncio.create_task(discovery_loop())
        logger.info("discovery scheduler started")

    # Is real intelligence actually on? Probe in the background so a slow or
    # unreachable gateway cannot delay startup — the result is logged loudly
    # and served at /health/models for the UI's mode badge.
    from app.llm import availability

    probe = asyncio.create_task(availability.log_at_startup())

    yield
    for pending in (task, probe):
        if pending is not None:
            pending.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="BidProof API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in get_settings().cors_origins.split(",")
            if origin.strip()
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(tenders.router)
    app.include_router(discovery.router)
    app.include_router(radar.router)
    app.include_router(rules.router)
    app.include_router(capability.router)
    app.include_router(checks.router)
    app.include_router(decision.router)
    app.include_router(console.router)
    app.include_router(amendment.router)
    app.include_router(questions.router)
    app.include_router(proposal.router)
    app.include_router(declarations.router)
    app.include_router(submission.router)
    app.include_router(chat.router)
    app.include_router(admin.router)
    app.include_router(analytics.router)
    app.include_router(modellab.router)
    app.include_router(onboarding.router)
    return app


app = create_app()
