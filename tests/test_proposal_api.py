"""US-09 integration: draft after GO with every factual sentence tagged and
verified; blocked without GO; a fabricating writer is dropped; a
contradicting writer is flagged; library quarantine; RLS; timing."""

import json

import pytest
from sqlalchemy import text

from test_checking_api import client_for, make_app, seed_and_upload
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration

FIFTEEN_MINUTES_MS = 15 * 60 * 1000


async def go_tender(client):
    tender_id = await seed_and_upload(client)
    await client.post(f"/tenders/{tender_id}/extract")
    await client.post(f"/tenders/{tender_id}/check")
    decision = (
        await client.post(f"/tenders/{tender_id}/decide",
                          json={"tender_value_inr": 5e7})
    ).json()
    assert decision["recommendation"] == "go"
    return tender_id


async def test_full_draft_after_go_all_claims_verified(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id = await go_tender(client)
        # A title with digits (the tender's own reference) must not read as an
        # unverifiable company claim.
        await owner_conn.execute(
            text("UPDATE tenders SET title = 'Tender 42/2026' WHERE id = :t"),
            {"t": __import__("uuid").UUID(tender_id)},
        )
        await owner_conn.commit()
        summary = (await client.post(f"/tenders/{tender_id}/proposal")).json()
        proposal = (await client.get(f"/tenders/{tender_id}/proposal")).json()

    assert summary["sections"] == 7
    assert summary["claims"] > 0
    assert summary["contradicted"] == 0
    assert summary["cannot_verify"] == 0
    assert summary["verified"] == summary["claims"]
    assert summary["duration_ms"] < FIFTEEN_MINUTES_MS   # the <15 min AC
    assert proposal["duration_ms"] == summary["duration_ms"]

    for section in proposal["sections"]:
        assert section["content"].strip()
        for claim in section["claims"]:
            assert claim["status"] == "verified"
            assert claim["source_tag"]                    # every claim cited


async def test_proposal_blocked_without_go(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id = await seed_and_upload(client)   # parsed, but no decision
        response = await client.post(f"/tenders/{tender_id}/proposal")
    assert response.status_code == 409
    assert "GO decision" in response.json()["detail"]


async def test_fabricating_writer_is_dropped_and_contradiction_flagged(owner_conn):
    """The strong model tries to (a) invent an untagged client name with
    numbers and (b) misquote a tagged fact. (a) is dropped by enforcement;
    (b) survives enforcement but the FactChecker marks it contradicted."""
    org_id = await create_org(owner_conn)

    class ScriptedWriter(FakeGateway):
        async def complete(self, role, messages, **params):
            if role != "strong":
                return await super().complete(role, messages, **params)
            self.calls.append({"role": role, "messages": messages})
            user = messages[1]["content"]
            # find a real fact tag to misuse for the contradiction
            import re

            tag = re.search(r"\[F:[0-9a-f]{8}\]", user)
            body = (
                "We supplied 999 warehouses for Fabricated Client Ltd in 2019.\n"
                + (f"Our turnover is ₹777.00 crore. {tag.group(0)}\n" if tag else "")
                + "We remain committed to quality."
            )
            return {"choices": [{"message": {"content": body}}]}

    gateway = ScriptedWriter(['{"rules": []}'])
    app = make_app(gateway)

    async with client_for(app, org_id) as client:
        tender_id = await go_tender(client)
        summary = (await client.post(f"/tenders/{tender_id}/proposal")).json()
        proposal = (await client.get(f"/tenders/{tender_id}/proposal")).json()

    assert summary["dropped_untagged"] >= 7      # the fabricated line, per section
    assert summary["contradicted"] >= 1          # the misquoted turnover
    all_text = json.dumps(proposal)
    assert "Fabricated Client" not in all_text   # thrown away, not down-scored

    flagged = [
        c for s in proposal["sections"] for c in s["claims"]
        if c["status"] == "contradicted"
    ]
    assert flagged and "777" in flagged[0]["text"]


async def test_library_upload_quarantined_and_seed_retrievable(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))

    async with client_for(app, org_id) as client:
        uploaded = await client.post("/library/proposals", json={
            "text": "Company Profile\nThirty years of storage systems.\n\n"
                    "Technical Approach\nRacking engineered to IS 4923 standards.",
            "outcome": "won", "source_name": "CWC 2024 bid",
        })
        assert uploaded.status_code == 201
        assert uploaded.json()["quarantined"] is True

        visible = (await client.get("/library/blocks")).json()
        everything = (
            await client.get("/library/blocks", params={"include_quarantined": True})
        ).json()

    assert visible == []                          # quarantined → not retrievable
    assert len(everything) == uploaded.json()["blocks"]
    assert all(b["quarantined"] for b in everything)


async def test_proposal_respects_rls(owner_conn, app_engine):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_a) as client:
        tender_id = await go_tender(client)
        await client.post(f"/tenders/{tender_id}/proposal")

    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_b)},
        )
        for table in ("proposals", "proposal_sections", "library_blocks"):
            count = (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar()
            assert count == 0


async def test_agent_runs_recorded_for_proposal(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id = await go_tender(client)
        await client.post(f"/tenders/{tender_id}/proposal")
        console = (await client.get(f"/tenders/{tender_id}/agent-runs")).json()

    agents = {r["agent"] for r in console["runs"]}
    assert {"librarian", "proposal_writer", "factchecker"} <= agents
