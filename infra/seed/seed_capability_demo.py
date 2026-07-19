"""Seed the demo org's capability database with SYNTHETIC data.

Every source field says so — real entries come from the annual report and
the PIM/SAP export (SPEC §5.4, §21), entered via the API or, later, the
onboarding wizard (US-17).

Run:  python -m uv run --project apps/api python infra/seed/seed_capability_demo.py
"""

import asyncio
import uuid
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

OWNER = "postgresql+asyncpg://bidproof_owner:bidproof_dev@localhost:5433/bidproof"
SRC_FACTS = "synthetic demo data — replace from annual report"
SRC_PRODUCTS = "synthetic demo data — replace from PIM export"
VERIFIED = date(2026, 7, 1)

FACTS = [
    dict(fact_type="turnover", legal_entity="Demo Manufacturing Co Ltd",
         fiscal_year="2022-23", value_number=1_200_000_000, unit="inr"),
    dict(fact_type="turnover", legal_entity="Demo Manufacturing Co Ltd",
         fiscal_year="2023-24", value_number=1_350_000_000, unit="inr"),
    dict(fact_type="turnover", legal_entity="Demo Manufacturing Co Ltd",
         fiscal_year="2024-25", value_number=1_500_000_000, unit="inr"),
    dict(fact_type="net_worth", value_number=2_100_000_000, unit="inr"),
    dict(fact_type="certification", value_text="ISO 9001:2015",
         valid_until=date(2027, 8, 31)),
    dict(fact_type="certification", value_text="ISO 14001:2015",
         valid_until=date(2026, 11, 30)),
    dict(fact_type="msme_status", value_text="not_msme"),
    dict(fact_type="blacklist_status", value_text="none"),
    dict(fact_type="past_order", value_text="Industrial racking, Central Warehousing Corp",
         value_number=38_000_000, unit="inr",
         details={"year": 2024, "completed": True}),
    dict(fact_type="past_order", value_text="Mezzanine storage systems, state PSU",
         value_number=52_000_000, unit="inr",
         details={"year": 2025, "completed": True}),
]

PRODUCTS = [
    dict(product_code="RACK-HD-01", product_name="Heavy-duty pallet rack",
         category="storage racks",
         specs={"load_capacity_kg": 2000, "height_mm": 4500},
         standards=["IS 4923", "ISO 9001"], lead_time_days=45,
         plant="Demo Plant 1", capacity_per_month=500,
         price_band_inr={"min_inr": 18000, "max_inr": 42000}),
    dict(product_code="RACK-MD-02", product_name="Medium-duty long-span shelving",
         category="storage racks",
         specs={"load_capacity_kg": 800, "height_mm": 3000},
         standards=["ISO 9001"], lead_time_days=30,
         plant="Demo Plant 1", capacity_per_month=900,
         price_band_inr={"min_inr": 9000, "max_inr": 21000}),
    dict(product_code="MEZZ-01", product_name="Modular mezzanine floor system",
         category="mezzanine systems",
         specs={"load_capacity_kg_m2": 500},
         standards=["IS 800", "ISO 9001"], lead_time_days=75,
         plant="Demo Plant 2", capacity_per_month=12,
         price_band_inr={"min_inr": 900000, "max_inr": 4500000}),
]


async def main() -> None:
    from app.models import CatalogueProduct, CompanyFact

    engine = create_async_engine(OWNER)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org_id = (
            await session.execute(
                text("SELECT id FROM organizations WHERE slug = 'demo-org'")
            )
        ).scalar()
        if org_id is None:
            raise SystemExit("demo-org not found — run the org seed first")

        existing = (
            await session.execute(
                select(CompanyFact.id).where(CompanyFact.org_id == org_id).limit(1)
            )
        ).first()
        if existing:
            print("capability data already seeded — leaving it untouched")
            return

        for fact in FACTS:
            session.add(
                CompanyFact(
                    org_id=org_id, source=SRC_FACTS, verified_at=VERIFIED, **fact
                )
            )
        for product in PRODUCTS:
            session.add(
                CatalogueProduct(
                    org_id=org_id, source=SRC_PRODUCTS, verified_at=VERIFIED, **product
                )
            )
        await session.commit()
        print(f"seeded {len(FACTS)} facts + {len(PRODUCTS)} products for {org_id}")
    await engine.dispose()


asyncio.run(main())
