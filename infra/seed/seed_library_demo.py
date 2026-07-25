"""Seed the demo org's proposal library with a SYNTHETIC starter set
(SPEC §5.7 fallback). Every block is tagged outcome='synthetic' and is
pre-approved (quarantined=false) so the ProposalWriter can retrieve it —
real won/lost proposals replace these later, and arrive quarantined.

Run:  python -m uv run --project apps/api python infra/seed/seed_library_demo.py
"""

import asyncio
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

OWNER = "postgresql+asyncpg://bidproof_owner:bidproof_dev@localhost:5433/bidproof"

BLOCKS = [
    ("company_profile",
     "The bidder is an established manufacturer of industrial storage and "
     "material-handling systems, with a nationwide installation and service "
     "network and a track record of executing large government supply orders "
     "on schedule."),
    ("technical_approach",
     "Offered systems are engineered to the relevant Indian and ISO standards. "
     "Fabrication is carried out in-house under a certified quality management "
     "system, and installation is performed by trained crews using calibrated "
     "tooling with documented load testing on completion."),
    ("delivery_and_support",
     "Delivery is scheduled against the purchase order with pan-India logistics. "
     "A dedicated support desk handles warranty and spares, and preventive "
     "maintenance visits are offered through the warranty period."),
    ("declarations",
     "The bidder declares that all information furnished is true, that it is not "
     "blacklisted by any government agency, and that it accepts the tender terms "
     "except where a pre-bid clarification has been sought."),
]


async def main() -> None:
    from app.models import LibraryBlockRow

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
                select(LibraryBlockRow.id)
                .where(LibraryBlockRow.org_id == org_id).limit(1)
            )
        ).first()
        if existing:
            print("library already seeded — leaving it untouched")
            return

        for section_tag, block_text in BLOCKS:
            session.add(LibraryBlockRow(
                org_id=org_id, section_tag=section_tag, text=block_text,
                outcome="synthetic",
                source_name=f"synthetic starter set ({date.today()})",
                quarantined=False,   # pre-approved starter set
            ))
        await session.commit()
        print(f"seeded {len(BLOCKS)} synthetic library blocks for {org_id}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
