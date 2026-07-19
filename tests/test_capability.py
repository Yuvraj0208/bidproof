"""Capability DB (SPEC §5.4): provenance is unrepresentable to omit,
tenants are isolated, and the API round-trips with provenance surfaced."""

import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from test_upload_api import create_org

pytestmark = pytest.mark.integration


def client_for(org_id):
    from app.main import create_app

    return AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
        headers={"X-Org-Id": str(org_id)},
    )


FACT = {
    "fact_type": "turnover",
    "legal_entity": "Demo Manufacturing Co Ltd",
    "fiscal_year": "2024-25",
    "value_number": 1_500_000_000,
    "unit": "inr",
    "source": "synthetic demo data — replace from annual report",
    "verified_at": "2026-07-01",
}

PRODUCT = {
    "product_code": "RACK-HD-01",
    "product_name": "Heavy-duty pallet rack",
    "category": "storage racks",
    "specs": {"load_capacity_kg": 2000, "height_mm": 4500},
    "standards": ["IS 4923", "ISO 9001"],
    "lead_time_days": 45,
    "plant": "Demo Plant 1",
    "capacity_per_month": 500,
    "price_band_inr": {"min_inr": 18000, "max_inr": 42000},
    "source": "synthetic demo data — replace from PIM export",
    "verified_at": "2026-07-01",
}


async def test_fact_without_provenance_is_unrepresentable(owner_conn):
    org_id = await create_org(owner_conn)

    async def try_insert(source, verified):
        await owner_conn.execute(
            text(
                "INSERT INTO company_facts (org_id, fact_type, value_number,"
                " source, verified_at) VALUES (:o, 'turnover', 100, :s, :v)"
            ),
            {"o": org_id, "s": source, "v": verified},
        )

    for source, verified in ((None, date(2026, 7, 1)), ("   ", date(2026, 7, 1)),
                             ("annual report", None)):
        with pytest.raises((IntegrityError, DBAPIError)):
            await try_insert(source, verified)
        await owner_conn.rollback()

    await try_insert("annual report FY24-25 p.112", date(2026, 7, 1))
    await owner_conn.commit()


async def test_product_without_provenance_is_unrepresentable(owner_conn):
    org_id = await create_org(owner_conn)
    with pytest.raises((IntegrityError, DBAPIError)):
        await owner_conn.execute(
            text(
                "INSERT INTO product_catalogue (org_id, product_code,"
                " product_name, source, verified_at)"
                " VALUES (:o, 'X-1', 'Thing', '  ', '2026-07-01')"
            ),
            {"o": org_id},
        )
    await owner_conn.rollback()


async def test_bogus_fact_type_rejected(owner_conn):
    org_id = await create_org(owner_conn)
    with pytest.raises((IntegrityError, DBAPIError)):
        await owner_conn.execute(
            text(
                "INSERT INTO company_facts (org_id, fact_type, source, verified_at)"
                " VALUES (:o, 'vibes', 'somewhere', '2026-07-01')"
            ),
            {"o": org_id},
        )
    await owner_conn.rollback()


async def test_api_roundtrip_with_provenance(owner_conn):
    org_id = await create_org(owner_conn)
    async with client_for(org_id) as client:
        created = await client.post("/capability/facts", json=FACT)
        assert created.status_code == 201, created.text
        assert created.json()["source"].startswith("synthetic demo data")

        product = await client.post("/capability/products", json=PRODUCT)
        assert product.status_code == 201, product.text

        facts = (await client.get("/capability/facts")).json()
        products = (await client.get("/capability/products")).json()

    assert len(facts) == 1 and facts[0]["fiscal_year"] == "2024-25"
    assert facts[0]["verified_at"] == "2026-07-01"
    assert len(products) == 1
    assert products[0]["standards"] == ["IS 4923", "ISO 9001"]
    assert products[0]["price_band_inr"]["max_inr"] == 42000


async def test_duplicate_product_code_conflicts_within_org_only(owner_conn):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    async with client_for(org_a) as client:
        assert (await client.post("/capability/products", json=PRODUCT)).status_code == 201
        assert (await client.post("/capability/products", json=PRODUCT)).status_code == 409
    async with client_for(org_b) as client:
        assert (await client.post("/capability/products", json=PRODUCT)).status_code == 201


async def test_capability_isolated_by_rls(owner_conn, app_engine):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    async with client_for(org_a) as client:
        await client.post("/capability/facts", json=FACT)
        await client.post("/capability/products", json=PRODUCT)

    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_b)},
        )
        for table in ("company_facts", "product_catalogue"):
            count = (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar()
            assert count == 0, f"org B must not see org A rows in {table}"
