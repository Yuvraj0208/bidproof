"""US-06 integration: Checkpoint 4 never auto-passes, sign-off is a named
human, overrides need a written reason, and the audit log cannot be edited."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from test_checking_api import client_for, make_app, seed_and_upload
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration


async def decided_tender(client):
    tender_id = await seed_and_upload(client)
    await client.post(f"/tenders/{tender_id}/check")
    decision = (
        await client.post(f"/tenders/{tender_id}/decide",
                          json={"tender_value_inr": 5e7})
    ).json()
    return tender_id, decision


async def test_decision_is_born_pending_signoff(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        tender_id, decision = await decided_tender(client)
        brief = (await client.get(f"/tenders/{tender_id}/brief")).json()

    assert decision["status"] == "pending_signoff"     # never auto-passes
    assert decision["recommendation"] == "go"
    assert decision["ev_inr"] == 1_155_000.0           # exact fixture math
    assert len(decision["terms"]) == 3
    assert brief["decision"]["status"] == "pending_signoff"
    assert brief["verdict_counts"]


async def test_signoff_requires_named_human_and_is_audited(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        tender_id, _ = await decided_tender(client)

        nameless = await client.post(f"/tenders/{tender_id}/decision/signoff",
                                     json={"name": ""})
        assert nameless.status_code == 422

        signed = await client.post(f"/tenders/{tender_id}/decision/signoff",
                                   json={"name": "Priya N"})
        assert signed.status_code == 200
        assert signed.json()["status"] == "signed_off"
        assert signed.json()["signed_off_by"] == "Priya N"

    actions = (
        await owner_conn.execute(
            text("SELECT actor, action FROM audit_log ORDER BY created_at")
        )
    ).fetchall()
    assert ("system", "decision_computed") in [tuple(a) for a in actions]
    assert ("Priya N", "decision_signed_off") in [tuple(a) for a in actions]


async def test_override_requires_written_reason_and_is_audited(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        tender_id, _ = await decided_tender(client)

        no_reason = await client.post(f"/tenders/{tender_id}/decision/override",
                                      json={"name": "Bid Head", "recommendation": "no_go",
                                            "reason": "x"})
        assert no_reason.status_code == 422  # reason min length

        overridden = await client.post(
            f"/tenders/{tender_id}/decision/override",
            json={"name": "Bid Head", "recommendation": "no_go",
                  "reason": "strategic client conflict this quarter"},
        )
        assert overridden.status_code == 200
        body = overridden.json()
        assert body["status"] == "overridden"
        assert "OVERRIDDEN by Bid Head" in body["reason"]

    row = (
        await owner_conn.execute(
            text("SELECT details FROM audit_log WHERE action = 'decision_overridden'")
        )
    ).scalar_one()
    assert row["reason"] == "strategic client conflict this quarter"
    assert row["from"] == "go" and row["to"] == "no_go"


async def test_audit_log_is_append_only_for_the_app_role(owner_conn, app_engine):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        await decided_tender(client)

    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_id)},
        )
        with pytest.raises((ProgrammingError, DBAPIError)):
            await conn.execute(text("UPDATE audit_log SET actor = 'tampered'"))
    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_id)},
        )
        with pytest.raises((ProgrammingError, DBAPIError)):
            await conn.execute(text("DELETE FROM audit_log"))


async def test_hard_gate_no_on_failed_mandatory_rule(owner_conn):
    org_id = await create_org(owner_conn)  # NO capability data at all
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        from test_parser_ladder import DIGITAL

        response = await client.post(
            "/tenders/upload",
            files={"file": ("tender.pdf", DIGITAL, "application/pdf")},
        )
        tender_id = response.json()["tender_id"]
        await client.post(f"/tenders/{tender_id}/check")
        # required_standard is GAP (no cert on file) → eligibility family?
        # required_standard is technical; min_turnover is needs_human (not gap).
        # Force a gate case: give the org turnover facts far below requirement.
        await client.post("/capability/facts", json={
            "fact_type": "turnover", "fiscal_year": "2024-25",
            "value_number": 1_000_000, "unit": "inr",
            "source": "synthetic demo data", "verified_at": "2026-07-01",
        })
        await client.post(f"/tenders/{tender_id}/check")
        decision = (
            await client.post(f"/tenders/{tender_id}/decide",
                              json={"tender_value_inr": 5e9})
        ).json()

    assert decision["recommendation"] == "no_go"
    assert decision["ev_inr"] is None
    assert decision["gate_failed"][0]["key"] == "min_turnover"
