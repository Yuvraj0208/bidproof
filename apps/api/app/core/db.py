"""Database access. Every request-scoped session carries the tenant's org id
as a transaction-local setting; row-level security policies key off it, so a
session can only ever see its own organization's rows."""

from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.tenancy import require_org_id

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


async def get_org_session(
    org_id: UUID = Depends(require_org_id),
) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            # set_config(..., true) == SET LOCAL: the org context exists only
            # inside this transaction and cannot leak across requests.
            await session.execute(
                text("SELECT set_config('app.current_org_id', :org_id, true)"),
                {"org_id": str(org_id)},
            )
            yield session
