from fastapi import FastAPI

from app.routers import health, tenders


def create_app() -> FastAPI:
    app = FastAPI(title="BidProof API", version="0.1.0")
    app.include_router(health.router)
    app.include_router(tenders.router)
    return app


app = create_app()
