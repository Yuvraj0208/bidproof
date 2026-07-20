"""US-08 integration: failed rules yield grounded cited letters, batched with
the query deadline; passing rules produce none; nothing is ever sent; RLS."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from test_checking_api import CERT_FACT, client_for, make_app, seed_and_upload
from test_parser_ladder import DIGITAL
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration


async def test_failed_rule_yields_grounded_cited_letter(owner_conn):
    # An org with NO capability data fails required_standard (GAP) and more.
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_id) as client:
        response = await client.post(
            "/tenders/upload",
            files={"file": ("tender.pdf", DIGITAL, "application/pdf")},
        )
        tender_id = response.json()["tender_id"]
        await client.post(f"/tenders/{tender_id}/check")
        summary = (await client.post(f"/tenders/{tender_id}/questions")).json()
        letters = (await client.get(f"/tenders/{tender_id}/questions")).json()

    assert summary["letters"] >= 1
    by_key = {letter["rule_key"]: letter for letter in letters}
    assert "required_standard" in by_key       # ISO 9001 GAP → a letter
    letter = by_key["required_standard"]
    assert letter["page_no"] >= 1
    assert letter["el_id"]                       # cites a real element
    assert f"page {letter['page_no']}" in letter["body"]
    assert "ISO 9001" in letter["body"]
    assert letter["status"] == "draft"           # never 'sent'


async def test_passing_rules_produce_no_letter(owner_conn):
    # Seed capability so eligibility/technical rules COMPLY → nothing to query.
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id = await seed_and_upload(client)   # facts + cert + product
        await client.post(f"/tenders/{tender_id}/check")
        await client.post(f"/tenders/{tender_id}/questions")
        letters = (await client.get(f"/tenders/{tender_id}/questions")).json()

    # digital.pdf is fully satisfiable by the seeded capability → no GAPs.
    assert all(letter["rule_key"] != "min_turnover" for letter in letters)
    assert letters == []


async def test_query_deadline_is_batched_onto_letters(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_id) as client:
        response = await client.post(
            "/tenders/upload",
            files={"file": ("tender.pdf", DIGITAL, "application/pdf")},
        )
        tender_id = response.json()["tender_id"]
        # give the tender a closing date so a deadline can be computed
        await owner_conn.execute(
            text("UPDATE tenders SET closing_at = :c WHERE id = :t"),
            {"c": datetime(2026, 9, 1, tzinfo=timezone.utc), "t": uuid.UUID(tender_id)},
        )
        await owner_conn.commit()
        await client.post(f"/tenders/{tender_id}/check")
        summary = (await client.post(f"/tenders/{tender_id}/questions")).json()

    # prebid_query_window_days = 14 in the fixture → 2026-09-01 minus 14 days.
    assert summary["query_deadline"] == "2026-08-18"


async def test_no_send_endpoint_exists(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    routes = {getattr(r, "path", "") for r in app.routes}
    assert not any(
        "send" in path or "email" in path or "submit" in path for path in routes
    ), "there must be no endpoint that sends a query letter"


async def test_letters_respect_rls(owner_conn, app_engine):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_a) as client:
        response = await client.post(
            "/tenders/upload",
            files={"file": ("tender.pdf", DIGITAL, "application/pdf")},
        )
        tender_id = response.json()["tender_id"]
        await client.post(f"/tenders/{tender_id}/check")
        await client.post(f"/tenders/{tender_id}/questions")

    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_b)},
        )
        count = (await conn.execute(text("SELECT count(*) FROM query_letters"))).scalar()
    assert count == 0
