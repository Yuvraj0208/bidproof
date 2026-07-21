"""US-16 unit tests: the role permission matrix — a role can never exceed its
permissions, and admin outranks the acting chain."""

import pytest
from fastapi import HTTPException

from app.core.roles import Role, require_role


async def _call(dep, role_value):
    return await dep(x_role=role_value)


async def test_higher_rank_satisfies_a_lower_requirement():
    dep = require_role(Role.BID_HEAD)
    assert await _call(dep, "bid_head") == Role.BID_HEAD
    assert await _call(dep, "admin") == Role.ADMIN     # admin outranks


async def test_lower_rank_is_refused():
    dep = require_role(Role.BID_HEAD)
    for role in ("viewer", "bid_executive", "reviewer"):
        with pytest.raises(HTTPException) as exc:
            await _call(dep, role)
        assert exc.value.status_code == 403


async def test_default_role_is_least_privilege():
    dep = require_role(Role.REVIEWER)
    with pytest.raises(HTTPException):
        await _call(dep, None)   # no header → viewer → refused


async def test_auditor_only_granted_where_listed():
    # auditor is outside the acting chain: allowed for audit, refused to act
    audit_dep = require_role(Role.AUDITOR, Role.ADMIN)
    assert await _call(audit_dep, "auditor") == Role.AUDITOR

    act_dep = require_role(Role.BID_HEAD)
    with pytest.raises(HTTPException):
        await _call(act_dep, "auditor")   # cannot sign off a bid


async def test_unknown_role_is_rejected():
    dep = require_role(Role.VIEWER)
    with pytest.raises(HTTPException) as exc:
        await _call(dep, "supreme_leader")
    assert exc.value.status_code == 400
