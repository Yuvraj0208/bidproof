import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.routers import (
    admin,
    amendment,
    analytics,
    capability,
    chat,
    checks,
    conductor as conductor_router,
    console,
    declarations,
    decision,
    discovery,
    evaluation,
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


def _disable_third_party_tracing() -> None:
    """Keep tender data inside our own tracing.

    LangGraph brings LangChain's tracer in as a transitive dependency. It is
    inert without keys, but "inert unless someone sets an environment
    variable" is a weak guarantee for tenant-confidential tender text, and the
    variable is one a developer might set for unrelated reasons. SPEC §13 names
    Langfuse as the tracer; this makes the other one off by assertion rather
    than by default.
    """
    for name in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_OTEL_ENABLED"):
        os.environ[name] = "false"


@asynccontextmanager
async def lifespan(app: FastAPI):
    _disable_third_party_tracing()
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

    # Close out any parse left mid-flight by the previous process, so the
    # console never shows a run that is "still going" when nothing is.
    async def _reap() -> None:
        from app.services.ingest import reap_interrupted_parse_runs

        try:
            reaped = await reap_interrupted_parse_runs()
            if reaped:
                logger.warning(
                    "closed %d parse run(s) interrupted by a restart", reaped
                )
        except Exception as exc:
            logger.warning("could not reap interrupted parse runs: %s", exc)

    reaper = asyncio.create_task(_reap())

    yield
    for pending in (task, probe, reaper):
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
    # Starlette's ServerErrorMiddleware sits OUTSIDE the CORS middleware, so an
    # unhandled exception produces a bare 500 with no Access-Control-Allow-Origin
    # header. The browser cannot read such a response and reports it as
    # "TypeError: Failed to fetch" — a network error, which is exactly the wrong
    # thing to go looking for. Handling the exception here means the response
    # travels back through CORS and the real status reaches the client.
    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "internal server error — check the API log"},
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
    app.include_router(conductor_router.router)
    app.include_router(amendment.router)
    app.include_router(questions.router)
    app.include_router(proposal.router)
    app.include_router(declarations.router)
    app.include_router(submission.router)
    app.include_router(chat.router)
    app.include_router(admin.router)
    app.include_router(analytics.router)
    app.include_router(evaluation.router)
    app.include_router(modellab.router)
    app.include_router(onboarding.router)
    return app


app = create_app()
