"""US-11 integration: three scores per section, individual approval gated on
open flags, edit-to-resolve, no approve-all, and readiness only when every
section is approved."""

import re

import pytest

from test_checking_api import client_for, make_app, seed_and_upload
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration


class ContradictingWriter(FakeGateway):
    """Polishes every fact-bearing section into a misquoted (contradicted)
    claim, so each section carries an open flag to resolve."""

    async def complete(self, role, messages, **params):
        if role != "strong":
            return await super().complete(role, messages, **params)
        self.calls.append({"role": role})
        tag = re.search(r"\[SRC: [^\]]+\]|\[F:[0-9a-f]{8}\]", messages[1]["content"])
        body = f"Our turnover is exactly 777 crore. {tag.group(0)}" if tag else ""
        return {"choices": [{"message": {"content": body}}]}


async def go_and_draft(client, gateway_cls=FakeGateway):
    tender_id = await seed_and_upload(client)
    await client.post(f"/tenders/{tender_id}/extract")
    await client.post(f"/tenders/{tender_id}/check")
    decision = (
        await client.post(f"/tenders/{tender_id}/decide",
                          json={"tender_value_inr": 5e7})
    ).json()
    assert decision["recommendation"] == "go"
    await client.post(f"/tenders/{tender_id}/proposal")
    return tender_id


async def test_sections_carry_three_scores(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        tender_id = await go_and_draft(client)
        proposal = (await client.get(f"/tenders/{tender_id}/proposal")).json()

    for section in proposal["sections"]:
        assert "verified_pct" in section
        assert "requirements_covered_pct" in section
        assert "style_match_pct" in section
    # at least one section actually addresses the tender's requirements
    assert any(
        (s["requirements_covered_pct"] or 0) > 0 for s in proposal["sections"]
    )


async def test_no_approve_all_endpoint_exists(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    paths = {getattr(r, "path", "") for r in app.routes}
    assert not any(
        "approve-all" in p or "approve_all" in p or p.endswith("/sections/approve")
        for p in paths
    ), "there must be no bulk approve-all endpoint"


async def test_approve_one_section_leaves_others_unapproved(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        tender_id = await go_and_draft(client)
        sections = (await client.get(f"/tenders/{tender_id}/proposal")).json()["sections"]
        first = sections[0]

        approved = await client.post(
            f"/tenders/{tender_id}/proposal/sections/{first['id']}/approve",
            json={"name": "Priya N"},
        )
        assert approved.status_code == 200
        assert approved.json()["approved"] is True
        assert approved.json()["approved_by"] == "Priya N"

        after = (await client.get(f"/tenders/{tender_id}/proposal")).json()["sections"]
        approved_flags = {s["id"]: s["approved"] for s in after}
        assert approved_flags[first["id"]] is True
        assert sum(1 for v in approved_flags.values() if v) == 1  # only one


async def test_section_with_open_flag_cannot_be_approved_until_resolved(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(ContradictingWriter(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        tender_id = await go_and_draft(client, ContradictingWriter)
        sections = (await client.get(f"/tenders/{tender_id}/proposal")).json()["sections"]
        flagged = next(s for s in sections if s["open_flags"])

        blocked = await client.post(
            f"/tenders/{tender_id}/proposal/sections/{flagged['id']}/approve",
            json={"name": "Priya N"},
        )
        assert blocked.status_code == 409
        assert "unresolved flag" in blocked.json()["detail"]

        # The human edits the section to remove the contradiction.
        edited = await client.put(
            f"/tenders/{tender_id}/proposal/sections/{flagged['id']}",
            json={"content": "We are committed to timely and quality delivery."},
        )
        assert edited.status_code == 200
        assert edited.json()["open_flags"] == []
        assert edited.json()["approved"] is False   # edit un-approves

        now_ok = await client.post(
            f"/tenders/{tender_id}/proposal/sections/{flagged['id']}/approve",
            json={"name": "Priya N"},
        )
        assert now_ok.status_code == 200


async def test_readiness_requires_every_section_approved(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        tender_id = await go_and_draft(client)
        sections = (await client.get(f"/tenders/{tender_id}/proposal")).json()["sections"]

        before = (await client.get(f"/tenders/{tender_id}/proposal/readiness")).json()
        assert before["ready"] is False
        assert before["approved"] == 0

        for section in sections:
            await client.post(
                f"/tenders/{tender_id}/proposal/sections/{section['id']}/approve",
                json={"name": "Priya N"},
            )

        after = (await client.get(f"/tenders/{tender_id}/proposal/readiness")).json()
        assert after["ready"] is True
        assert after["approved"] == after["total"] == len(sections)
