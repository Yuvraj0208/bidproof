"""Shared fixtures.

Unit tests need nothing external. Tests marked `integration` need a live
Postgres reachable via DATABASE_URL_OWNER / DATABASE_URL (docker compose up,
or the CI service container); they bootstrap the app role, run migrations,
and clean tables between tests.
"""

import asyncio
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

OWNER_URL = os.environ.get(
    "DATABASE_URL_OWNER",
    "postgresql+asyncpg://bidproof_owner:bidproof_dev@localhost:5433/bidproof",
)
APP_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://bidproof_app:bidproof_app_dev@localhost:5433/bidproof",
)

# The app role's dev password. Local/CI only — real deployments set their own.
APP_ROLE_BOOTSTRAP = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bidproof_app') THEN
        CREATE ROLE bidproof_app LOGIN PASSWORD 'bidproof_app_dev';
    END IF;
END
$$;
"""


def _bootstrap_database() -> None:
    """Create the app role, extensions, and schema (as owner)."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def prepare() -> None:
        engine = create_async_engine(OWNER_URL, isolation_level="AUTOCOMMIT")
        async with engine.connect() as conn:
            await conn.execute(text(APP_ROLE_BOOTSTRAP))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(
                text("GRANT CONNECT ON DATABASE bidproof TO bidproof_app")
            )
            await conn.execute(text("GRANT USAGE ON SCHEMA public TO bidproof_app"))
        await engine.dispose()

    asyncio.run(prepare())

    alembic_cfg = Config(str(REPO_ROOT / "apps" / "api" / "alembic.ini"))
    os.environ.setdefault("DATABASE_URL_OWNER", OWNER_URL)
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="session")
def db_bootstrap():
    _bootstrap_database()


@pytest.fixture
async def owner_conn(db_bootstrap):
    """Superuser/owner connection — bypasses RLS; used only to seed/inspect."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(OWNER_URL)
    async with engine.connect() as conn:
        await conn.execute(text("TRUNCATE tenders, organizations CASCADE"))
        await conn.commit()
        yield conn
        await conn.rollback()
        await conn.execute(text("TRUNCATE tenders, organizations CASCADE"))
        await conn.commit()
    await engine.dispose()


@pytest.fixture
async def app_engine(db_bootstrap):
    """Engine connected as the RLS-constrained application role."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(APP_URL)
    yield engine
    await engine.dispose()
