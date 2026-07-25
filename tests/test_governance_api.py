"""US-16 integration: role enforcement on sensitive actions, the auditor's
read of the append-only log, and a logged model swap."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from test_checking_api import client_for, make_app, seed_and_upload
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration


def role_client(app, org_id, role):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Org-Id": str(org_id), "X-Role": role},
    )


async def decided_tender(client):
    tender_id = await seed_and_upload(client)
    await client.post(f"/tenders/{tender_id}/extract")
    await client.post(f"/tenders/{tender_id}/check")
    await client.post(f"/tenders/{tender_id}/decide", json={"tender_value_inr": 5e7})
    return tender_id


async def test_viewer_cannot_sign_off_but_bid_head_can(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as setup:   # default role fine for setup
        tender_id = await decided_tender(setup)

    async with role_client(app, org_id, "viewer") as viewer:
        refused = await viewer.post(f"/tenders/{tender_id}/decision/signoff",
                                    json={"name": "V"})
        assert refused.status_code == 403

    async with role_client(app, org_id, "bid_head") as head:
        ok = await head.post(f"/tenders/{tender_id}/decision/signoff",
                             json={"name": "Bid Head"})
        assert ok.status_code == 200
        assert ok.json()["status"] == "signed_off"


async def test_only_reviewer_can_lift_library_quarantine(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    async with client_for(app, org_id) as setup:
        block = (await setup.post("/library/blocks", json={
            "section_tag": "company_profile",
            "text": "We are an established manufacturer with a strong record.",
            "outcome": "won", "source_name": "past bid",
        })).json()
        block_id = block["id"]

    async with role_client(app, org_id, "bid_executive") as junior:
        refused = await junior.post(f"/library/blocks/{block_id}/approve")
        assert refused.status_code == 403

    async with role_client(app, org_id, "reviewer") as reviewer:
        ok = await reviewer.post(f"/library/blocks/{block_id}/approve")
        assert ok.status_code == 200 and ok.json()["quarantined"] is False


async def test_auditor_reads_log_viewer_cannot(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as setup:
        tender_id = await decided_tender(setup)
    async with role_client(app, org_id, "bid_head") as head:
        await head.post(f"/tenders/{tender_id}/decision/signoff",
                        json={"name": "Bid Head"})

    async with role_client(app, org_id, "viewer") as viewer:
        assert (await viewer.get("/audit")).status_code == 403

    async with role_client(app, org_id, "auditor") as auditor:
        log = await auditor.get("/audit")
        assert log.status_code == 200
        actions = {e["action"] for e in log.json()}
        assert "decision_signed_off" in actions


async def test_model_swap_is_logged_admin_only(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))

    async with role_client(app, org_id, "reviewer") as reviewer:
        refused = await reviewer.post("/admin/model-swap", json={
            "role": "strong", "to_model": "some/new-model",
            "reason": "beat the incumbent on the gold set", "actor": "R"})
        assert refused.status_code == 403

    async with role_client(app, org_id, "admin") as admin:
        ok = await admin.post("/admin/model-swap", json={
            "role": "strong", "to_model": "some/new-model",
            "reason": "beat the incumbent on the gold set by 3 F1", "actor": "Admin"})
        assert ok.status_code == 200

    row = (
        await owner_conn.execute(
            text("SELECT actor, details FROM audit_log WHERE action = 'model_swapped'")
        )
    ).one()
    assert row.actor == "Admin"
    assert row.details["role"] == "strong"
    assert row.details["to_model"] == "some/new-model"


async def test_export_override_requires_bid_head(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    # a tender with an unaddressed mandatory clause → export is blocked
    async with client_for(app, org_id) as setup:
        from test_parser_ladder import DIGITAL

        response = await setup.post(
            "/tenders/upload",
            files={"file": ("t.pdf", DIGITAL, "application/pdf")},
        )
        tender_id = response.json()["tender_id"]
        await setup.post(f"/tenders/{tender_id}/extract")
        await setup.post(f"/tenders/{tender_id}/check")

    async with role_client(app, org_id, "bid_executive") as exec_:
        refused = await exec_.post(
            f"/tenders/{tender_id}/proposal/export",
            json={"override_name": "X", "override_reason": "trust me on this"},
        )
        assert refused.status_code == 403   # override needs bid_head
