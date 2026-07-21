"""Checking integration: end-to-end verdicts against seeded capability data,
the no-model guarantee for arithmetic rules, and RLS."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from test_capability import FACT, PRODUCT
from test_parser_ladder import DIGITAL
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration


def make_app(gateway):
    from app.main import create_app
    from app.services.checking import get_checking_gateway
    from app.services.extraction import get_extraction_gateway
    from app.services.proposal import get_writer_gateway
    from app.services.questions import get_question_gateway

    app = create_app()
    # Every model-using dependency resolves to the test's fake gateway, so no
    # test ever reaches a real model endpoint.
    for provider in (get_extraction_gateway, get_checking_gateway,
                     get_question_gateway, get_writer_gateway):
        app.dependency_overrides[provider] = lambda: gateway
    return app


def client_for(app, org_id):
    # Default to the admin role so pipeline tests exercise the happy path;
    # role-enforcement tests (test_governance_api) pass an explicit X-Role.
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Org-Id": str(org_id), "X-Role": "admin"},
    )


CERT_FACT = {
    "fact_type": "certification",
    "value_text": "ISO 9001:2015",
    "valid_until": "2027-08-31",
    "source": "synthetic demo data",
    "verified_at": "2026-07-01",
}


async def seed_and_upload(client):
    assert (await client.post("/capability/facts", json=FACT)).status_code == 201
    assert (await client.post("/capability/facts", json=CERT_FACT)).status_code == 201
    assert (await client.post("/capability/products", json=PRODUCT)).status_code == 201
    response = await client.post(
        "/tenders/upload",
        files={"file": ("tender.pdf", DIGITAL, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["tender_id"]


async def test_checks_end_to_end_with_zero_model_calls(owner_conn):
    org_id = await create_org(owner_conn)
    gateway = FakeGateway(['{"rules": []}'])
    app = make_app(gateway)

    async with client_for(app, org_id) as client:
        tender_id = await seed_and_upload(client)
        summary = (await client.post(f"/tenders/{tender_id}/check")).json()
        verdicts = (await client.get(f"/tenders/{tender_id}/verdicts")).json()
        risks = (await client.get(f"/tenders/{tender_id}/risks")).json()

    assert summary["rules_checked"] >= 5
    # every rule in digital.pdf is arithmetic-checkable → the judge is
    # never consulted (the fake gateway saw only the extraction call)
    assert summary["model_calls"] == 0

    by_key = {v["key"]: v for v in verdicts}
    turnover = by_key["min_turnover"]
    assert turnover["verdict"] == "complies"        # ₹150 cr avg vs ₹5 cr required
    assert turnover["arithmetic"] is True
    assert turnover["cited_fact_id"] is not None
    assert turnover["bbox"]["x1"] > turnover["bbox"]["x0"]  # proof chain intact

    delivery = by_key["delivery_days"]
    assert delivery["verdict"] == "complies"        # 45-day lead vs 90 required
    assert delivery["cited_product_id"] is not None

    standard = by_key["required_standard"]
    assert standard["verdict"] == "complies"        # ISO 9001 valid to 2027

    assert by_key["emd_amount"]["verdict"] == "not_applicable"
    assert isinstance(risks, list)                  # no flags expected here


async def test_missing_capability_data_abstains_not_passes(owner_conn):
    org_id = await create_org(owner_conn)  # NO facts, NO products
    gateway = FakeGateway(['{"rules": []}'])
    app = make_app(gateway)

    async with client_for(app, org_id) as client:
        response = await client.post(
            "/tenders/upload",
            files={"file": ("tender.pdf", DIGITAL, "application/pdf")},
        )
        tender_id = response.json()["tender_id"]
        await client.post(f"/tenders/{tender_id}/check")
        verdicts = (await client.get(f"/tenders/{tender_id}/verdicts")).json()

    by_key = {v["key"]: v for v in verdicts}
    assert by_key["min_turnover"]["verdict"] == "needs_human"
    assert by_key["delivery_days"]["verdict"] == "needs_human"
    assert by_key["required_standard"]["verdict"] == "gap"


async def test_verdicts_and_risks_respect_rls(owner_conn, app_engine):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    gateway = FakeGateway(['{"rules": []}'])
    app = make_app(gateway)

    async with client_for(app, org_a) as client:
        tender_id = await seed_and_upload(client)
        await client.post(f"/tenders/{tender_id}/check")

    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_b)},
        )
        for table in ("verdicts", "risks"):
            count = (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar()
            assert count == 0
