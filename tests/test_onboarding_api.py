"""US-17 integration: a fresh org onboards end to end (org → facts CSV →
products CSV → profile → branding) and is immediately usable and isolated."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from test_checking_api import make_app
from test_parser_ladder import DIGITAL
from test_rules_api import FakeGateway

pytestmark = pytest.mark.integration

FACTS_CSV = (
    "fact_type,legal_entity,fiscal_year,value_text,value_number,unit,valid_until\n"
    "turnover,Newco Pvt Ltd,2024-25,,150000000,inr,\n"
    "certification,,,ISO 9001:2015,,,2027-08-31\n"
    "blacklist_status,,,none,,,\n"
)
PRODUCTS_CSV = (
    "product_code,product_name,category,standards,lead_time_days,plant,"
    "capacity_per_month,price_min_inr,price_max_inr\n"
    "RACK-HD-01,Heavy-duty pallet rack,storage racks,IS 4923|ISO 9001,45,"
    "Plant 1,500,18000,42000\n"
)
PROFILE = {
    "categories": [{"name": "storage racks", "keywords": ["storage", "rack", "warehouse"]}],
    "weights": {},
    "value_band_inr": {"min_inr": 10000000, "max_inr": 1000000000},
    "locations": [],
    "win_categories": ["storage racks"],
}


def client(app, org_id=None):
    headers = {"X-Role": "admin"}
    if org_id:
        headers["X-Org-Id"] = str(org_id)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                       headers=headers)


async def test_fresh_org_onboards_end_to_end_and_is_usable(owner_conn):
    app = make_app(FakeGateway(['{"rules": []}']))
    slug = f"newco-{uuid.uuid4().hex[:8]}"

    async with client(app) as anon:
        created = await anon.post("/onboarding/org",
                                  json={"name": "Newco Pvt Ltd", "slug": slug})
        assert created.status_code == 201
        org_id = created.json()["org_id"]

        # the CSV template is provided
        template = await anon.get("/onboarding/templates/products.csv")
        assert template.status_code == 200 and "product_code" in template.text

    async with client(app, org_id) as c:
        assert (await c.post("/onboarding/facts",
                             files={"file": ("facts.csv", FACTS_CSV.encode(),
                                             "text/csv")})).json()["facts_loaded"] == 3
        assert (await c.post("/onboarding/products",
                             files={"file": ("products.csv", PRODUCTS_CSV.encode(),
                                             "text/csv")})).json()["products_loaded"] == 1
        assert (await c.post("/onboarding/profile", json=PROFILE)).status_code == 200
        finished = await c.post("/onboarding/branding",
                                json={"primary_color": "#4B0082", "finish": True})
        assert finished.json()["onboarded"] is True

        status = (await c.get("/onboarding/status")).json()
        assert status["ready"] is True and status["onboarded"] is True
        assert all(status["steps"].values())

        # immediately usable: upload a tender → it triages into the lane and
        # checks against the just-loaded capability
        up = await c.post("/tenders/upload",
                          files={"file": ("t.pdf", DIGITAL, "application/pdf")})
        tender_id = up.json()["tender_id"]
        await c.post(f"/tenders/{tender_id}/check")
        verdicts = (await c.get(f"/tenders/{tender_id}/verdicts")).json()
        by_key = {v["key"]: v for v in verdicts}

    # the onboarded facts drive a real verdict
    assert by_key["min_turnover"]["verdict"] == "complies"   # ₹15cr from the CSV
    assert by_key["required_standard"]["verdict"] == "complies"  # ISO 9001 cert


async def test_duplicate_slug_is_refused(owner_conn):
    app = make_app(FakeGateway([]))
    slug = f"dup-{uuid.uuid4().hex[:8]}"
    async with client(app) as anon:
        assert (await anon.post("/onboarding/org",
                                json={"name": "Org A", "slug": slug})).status_code == 201
        again = await anon.post("/onboarding/org", json={"name": "Org B", "slug": slug})
        assert again.status_code == 409


async def test_onboarded_org_is_isolated(owner_conn, app_engine):
    app = make_app(FakeGateway([]))
    async with client(app) as anon:
        a = (await anon.post("/onboarding/org",
                             json={"name": "Org A", "slug": f"a-{uuid.uuid4().hex[:8]}"})).json()
    async with client(app, a["org_id"]) as c:
        await c.post("/onboarding/facts",
                     files={"file": ("f.csv", FACTS_CSV.encode(), "text/csv")})

    # a brand-new second org sees none of org A's data
    async with client(app) as anon:
        b = (await anon.post("/onboarding/org",
                             json={"name": "Org B", "slug": f"b-{uuid.uuid4().hex[:8]}"})).json()
    async with client(app, b["org_id"]) as c:
        facts = (await c.get("/capability/facts")).json()
    assert facts == []
