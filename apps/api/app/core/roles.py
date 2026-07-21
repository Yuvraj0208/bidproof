"""Roles and permissions (US-16, SPEC §14).

Six roles: viewer / bid_executive / reviewer / bid_head / admin / auditor.
Like the org context, the role arrives in a header (X-Role) as a temporary
stand-in until real authenticated sessions land — it stays a hard gate either
way. A role can never exceed its permissions.
"""

from enum import Enum

from fastapi import Header, HTTPException


class Role(str, Enum):
    VIEWER = "viewer"
    BID_EXECUTIVE = "bid_executive"
    REVIEWER = "reviewer"
    BID_HEAD = "bid_head"
    ADMIN = "admin"
    AUDITOR = "auditor"


# The linear chain of acting power. Auditor sits outside it — a read + audit
# role that can never act on a bid.
_RANK = {
    Role.VIEWER: 0,
    Role.BID_EXECUTIVE: 1,
    Role.REVIEWER: 2,
    Role.BID_HEAD: 3,
    Role.ADMIN: 4,
}


def _role_from_header(x_role: str | None) -> Role:
    if x_role is None:
        return Role.VIEWER  # least privilege by default
    try:
        return Role(x_role.strip().lower())
    except ValueError:
        raise HTTPException(400, f"unknown role {x_role!r}")


def require_role(*allowed: Role):
    """Dependency: allow the listed roles, plus anyone ranked at or above the
    lowest listed acting role (admin outranks bid_head, etc.). Auditor is only
    granted where it is explicitly listed."""
    acting = [r for r in allowed if r in _RANK]
    floor = min((_RANK[r] for r in acting), default=None)

    async def dependency(x_role: str | None = Header(default=None)) -> Role:
        role = _role_from_header(x_role)
        if role in allowed:
            return role
        if floor is not None and role in _RANK and _RANK[role] >= floor:
            return role
        raise HTTPException(
            403,
            f"role '{role.value}' may not perform this action "
            f"(requires one of: {sorted(r.value for r in allowed)})",
        )

    return dependency
