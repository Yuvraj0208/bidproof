"""Tenant context (SPEC §15).

Temporary mechanism: the X-Org-Id header names the organization. US-16
replaces this with authenticated sessions and roles. It stays a hard
requirement either way — nothing runs without a tenant.
"""

from uuid import UUID

from fastapi import Header, HTTPException


async def require_org_id(x_org_id: str | None = Header(default=None)) -> UUID:
    if x_org_id is None:
        raise HTTPException(status_code=400, detail="X-Org-Id header is required")
    try:
        return UUID(x_org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Org-Id must be a valid UUID")


async def require_known_org(org_id: UUID) -> None:
    """Fail clearly when the header names an organization that no longer exists.

    A browser can hold a signed-in org id long after that row has gone — most
    easily by running the integration suite, whose fixtures TRUNCATE
    `organizations`. Writing against it hit a foreign-key violation deep in the
    request, which surfaced as an unhandled 500, and a 500 has no CORS header,
    so the browser reported "TypeError: Failed to fetch" and sent everyone
    hunting for a network fault.

    Reads do not need this: row-level security already scopes them to nothing,
    which is the correct answer for an unknown tenant. Only writes need to say
    so out loud.
    """
    from sqlalchemy import select

    from app.core.db import org_scoped_session
    from app.models import Organization

    async with org_scoped_session(org_id) as session:
        found = (
            await session.execute(select(Organization.id).where(Organization.id == org_id))
        ).first()
    if found is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "this organisation no longer exists — sign out and sign in again "
                "(its data may have been reset)"
            ),
        )
