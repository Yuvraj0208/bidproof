"""US-12 integration: a full run records every agent call with cost under
the tender's trace id, totals sum correctly, and replay re-executes."""

import pytest

from test_checking_api import client_for, make_app, seed_and_upload
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration

PIPELINE_AGENTS = {"parser", "triage", "extractor", "matcher", "riskscorer"}


async def test_full_run_records_every_agent_call(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id = await seed_and_upload(client)
        await client.post(f"/tenders/{tender_id}/decide",
                          json={"tender_value_inr": 5e7})
        console = (await client.get(f"/tenders/{tender_id}/agent-runs")).json()

    agents = {r["agent"] for r in console["runs"]}
    assert PIPELINE_AGENTS | {"decider"} <= agents

    for run in console["runs"]:
        assert run["trace_id"], "every call sits under the tender's trace id"
        assert run["duration_ms"] >= 0
        assert run["cost_inr"] >= 0
        assert run["status"] in ("ok", "failed")

    # Totals sum correctly — recomputed here independently.
    totals = console["totals"]
    assert totals["calls"] == len(console["runs"])
    assert totals["tokens"] == sum(
        r["tokens_in"] + r["tokens_out"] for r in console["runs"]
    )
    assert totals["cost_inr"] == round(
        sum(r["cost_inr"] for r in console["runs"]), 4
    )
    assert totals["duration_ms"] == sum(r["duration_ms"] for r in console["runs"])

    trace_ids = {r["trace_id"] for r in console["runs"]}
    assert len(trace_ids) == 1  # one trace follows the tender end to end


async def test_replay_reexecutes_the_pipeline(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}', '{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id = await seed_and_upload(client)
        before = (await client.get(f"/tenders/{tender_id}/agent-runs")).json()

        replayed = await client.post(f"/tenders/{tender_id}/replay")
        assert replayed.status_code == 200

        after = (await client.get(f"/tenders/{tender_id}/agent-runs")).json()
        verdicts = (await client.get(f"/tenders/{tender_id}/verdicts")).json()

    assert after["totals"]["calls"] >= before["totals"]["calls"] + len(PIPELINE_AGENTS)
    assert {r["trace_id"] for r in after["runs"]} == {
        r["trace_id"] for r in before["runs"]
    }, "replay stays under the same trace id"
    assert verdicts, "replay rebuilt the derived truth end to end"
