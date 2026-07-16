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
