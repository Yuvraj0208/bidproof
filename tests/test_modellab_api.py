"""US-14 integration: the Lab run is admin-gated, persists, and adopting a
winner is logged as a config event."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from test_checking_api import make_app
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration


def role_client(app, org_id, role):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Org-Id": str(org_id), "X-Role": role},
    )


async def test_lab_run_is_admin_only_and_persists(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))

    async with role_client(app, org_id, "reviewer") as reviewer:
        assert (await reviewer.post("/modellab/run",
                                    json={"role": "extraction"})).status_code == 403

    async with role_client(app, org_id, "admin") as admin:
        run = (await admin.post("/modellab/run", json={"role": "extraction"})).json()
        assert run["gold_tenders"] >= 25
        assert len(run["leaderboard"]) >= 2
        # a leaderboard with the money columns
        top = run["leaderboard"][0]
        assert {"model", "f1_overall", "hallucination_rate",
                "cost_per_tender_inr"} <= set(top)

        runs = (await admin.get("/modellab/runs")).json()
        assert len(runs) == 1 and runs[0]["leaderboard"]


async def test_adopting_a_winner_is_logged(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    async with role_client(app, org_id, "admin") as admin:
        await admin.post("/modellab/run", json={"role": "extraction"})
        adopted = await admin.post("/modellab/adopt", json={
            "gateway_role": "mid", "model": "deepseek-r1 (open)",
            "reason": "best F1 per rupee on our gold set", "actor": "Admin"})
        assert adopted.status_code == 200

    row = (
        await owner_conn.execute(
            text("SELECT actor, details FROM audit_log WHERE action = 'model_adopted'")
        )
    ).one()
    assert row.actor == "Admin"
    assert row.details["gateway_role"] == "mid"
    assert "deepseek" in row.details["model"]


async def test_lab_runs_respect_rls(owner_conn, app_engine):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    async with role_client(app, org_a, "admin") as admin:
        await admin.post("/modellab/run", json={"role": "extraction"})

    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_b)},
        )
        count = (
            await conn.execute(text("SELECT count(*) FROM model_lab_runs"))
        ).scalar()
    assert count == 0
