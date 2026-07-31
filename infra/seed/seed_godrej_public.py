"""Seed the capability database from Godrej's PUBLIC data (SPEC §5.4, §21).

    python -m uv run --project apps/api python infra/seed/seed_godrej_public.py

Why this file exists: the demo previously ran on an invented company ("Demo
Storage Co", ₹120 crore turnover). Godrej is the design partner, and their
Intralogistics business — storage racking and material handling — is exactly
what the demo tenders ask for, so the pilot is far more convincing on their own
numbers.

**Every fact here was retrieved from a public source and carries that source in
its `source` column.** Nothing is estimated, rounded or inferred. Where a figure
that the pipeline WANTS is not public — lead times, monthly capacity, past
contract values — it is deliberately left absent rather than invented. The
checker will then return `needs_human` for those criteria, which is the correct
and honest outcome: the product's whole promise is that it says "I do not know"
instead of guessing (SPEC §9 rule 1). Fill them from Godrej's own SAP/PIM export
or their reply to the §21 data-request email.

Run with --org-slug to seed a different tenant.
"""

import argparse
import asyncio
import json
import uuid
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

OWNER = "postgresql+asyncpg://bidproof_owner:bidproof_dev@localhost:5433/bidproof"

ORG_NAME = "Godrej Enterprises Group"
ORG_SLUG = "godrej"
LEGAL_ENTITY = "Godrej & Boyce Mfg. Co. Ltd."

# Provenance strings. These end up in the UI and in the exported .docx, so they
# name the actual page a figure came from.
SRC_PROFILE = (
    "public: godrejenterprises.com/about-us/corporate-profile "
    "(FY2024-25 figure stated as unaudited/provisional), retrieved 2026-07-26"
)
SRC_RACKING = (
    "public: godrejenterprises.com/intralogistics/storage-solution/"
    "racking-solutions, retrieved 2026-07-26"
)
SRC_WIKI = "public: en.wikipedia.org/wiki/Godrej_&_Boyce, retrieved 2026-07-26"
VERIFIED = date(2026, 7, 26)

FACTS = [
    # Group turnover. The FY2024-25 number is published as unaudited and
    # provisional — recorded as stated, not smoothed.
    dict(fact_type="turnover", legal_entity=LEGAL_ENTITY, fiscal_year="2024-25",
         value_number=189_700_000_000, unit="inr", source=SRC_PROFILE),
    dict(fact_type="turnover", legal_entity=LEGAL_ENTITY, fiscal_year="2023-24",
         value_number=163_550_000_000, unit="inr", source=SRC_PROFILE),
    dict(fact_type="turnover", legal_entity=LEGAL_ENTITY, fiscal_year="2021-22",
         value_number=118_000_000_000, unit="inr", source=SRC_WIKI),

    # Certifications held by the Intralogistics/storage business. ISO 45001
    # matters: government tenders increasingly demand it, and the synthetic
    # demo company did NOT hold it.
    #
    # No public expiry dates exist for these. `valid_until` is left NULL, which
    # the checker treats as "cannot confirm currency" — a human must attach the
    # certificate. Inventing an expiry date would be exactly the failure mode
    # this product is built to prevent.
    dict(fact_type="certification", value_text="ISO 9001", source=SRC_RACKING),
    dict(fact_type="certification", value_text="ISO 14001", source=SRC_RACKING),
    dict(fact_type="certification", value_text="ISO 45001", source=SRC_RACKING),
    dict(fact_type="certification", value_text="GreenPro", source=SRC_RACKING),

    # Founded 1897, 15,000+ employees and "200 million sq ft installed" are all
    # public and all relevant to experience criteria — but `company_facts`
    # constrains fact_type to six kinds (turnover, net_worth, certification,
    # msme_status, blacklist_status, past_order). Widening that CHECK is a schema
    # decision for a story of its own, not something a seed script should smuggle
    # in, so those three are left out rather than mislabelled as another type.
    dict(fact_type="blacklist_status", value_text="none",
         source="to be confirmed by Godrej — not a public fact"),
    dict(fact_type="msme_status", value_text="not_msme", source=SRC_WIKI),
]

# The eleven racking systems named on the public product pages, plus shelving.
#
# `lead_time_days` and `capacity_per_month` are NOT published anywhere. They are
# left as None on purpose: the delivery-schedule check will return needs_human
# rather than a number nobody can stand behind. Load ratings and standards ARE
# published, so those are filled.
_LOAD_NOTE = {"beam_pair_load_kg": 4000, "frame_load_tonnes_max": 35,
              "max_height_m": 50, "seismic_zone": 5}
_STANDARDS = ["EN 15512", "FEM", "RMI", "ISO 9001"]

# Godrej's own mark, and the crimson from it for the monogram fallback.
BRANDING = {
    "logo_url": "/godrej-logo.png",
    "primary_color": "#C7017F",
}


def _rack(code: str, name: str, category: str = "storage racks", **extra) -> dict:
    return dict(
        product_code=code, product_name=name, category=category,
        specs={**_LOAD_NOTE, **extra},
        standards=list(_STANDARDS),
        lead_time_days=None,        # not public — see module docstring
        capacity_per_month=None,    # not public
        plant="Godrej Storage Solutions (largest storage plant in Asia, per public site)",
        price_band_inr={},          # not public
        source=SRC_RACKING,
    )

PRODUCTS = [
    _rack("GSS-SPR", "Selective Pallet Racking", selectivity="100%"),
    _rack("GSS-DDPR", "Double Deep Pallet Racking"),
    _rack("GSS-VNA", "Very Narrow Aisle Pallet Racking"),
    _rack("GSS-MPR", "Mobile Pallet Racking"),
    _rack("GSS-SHUTTLE", "Shuttle Pallet Racking"),
    _rack("GSS-DRIVEIN", "Drive-In Pallet Racking"),
    _rack("GSS-PUSHBACK", "Push Back Pallet Racking"),
    _rack("GSS-FLOW", "Pallet Flow Racking"),
    _rack("GSS-CLAD", "Clad Rack Warehouse"),
    _rack("GSS-CANTI", "Cantilever Racking"),
    _rack("GSS-ASRS", "Pallet ASRS (crane-based)", category="automation"),
    _rack("GSS-SHELV", "Industrial Shelving System", category="shelving"),
]

PROFILE = {
    "categories": [
        {"name": "storage racks",
         "keywords": ["storage", "rack", "racking", "shelving", "pallet",
                      "warehouse", "godrej make", "slotted angle"]},
        {"name": "material handling",
         "keywords": ["material handling", "forklift", "intralogistics",
                      "trolley", "conveyor", "stacker"]},
        {"name": "office furniture",
         "keywords": ["furniture", "almirah", "cupboard", "workstation",
                      "chair", "table", "locker"]},
        {"name": "security solutions",
         "keywords": ["safe", "vault", "locker", "security", "lock"]},
    ],
    # These keys MUST match the scorer's component names exactly
    # (agents/triage/bidproof_triage/scoring.py): category, eligibility, value,
    # location, win_history. They were once written as category_fit/value_band/
    # past_wins, which the scorer never looked up — so the weights silently did
    # nothing AND doubled the coverage denominator, pinning every tender in the
    # "needs human" queue for ever.
    "weights": {
        "category": 0.35,
        "eligibility": 0.25,
        "value": 0.15,
        "location": 0.10,
        "win_history": 0.15,
    },
    # Godrej bids across a very wide range; the band is deliberately open.
    "value_band_inr": {"min_inr": 100_000, "max_inr": 50_000_000_000},
    "win_categories": ["storage racks", "material handling"],
}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-slug", default=ORG_SLUG)
    parser.add_argument("--org-name", default=ORG_NAME)
    args = parser.parse_args()

    from app.models import CatalogueProduct, CompanyFact, OrgProfile

    engine = create_async_engine(OWNER)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org_id = (
            await session.execute(
                text("SELECT id FROM organizations WHERE slug = :s"),
                {"s": args.org_slug},
            )
        ).scalar()
        if org_id is None:
            org_id = uuid.uuid4()
            await session.execute(
                text("INSERT INTO organizations (id, name, slug) "
                     "VALUES (:i, :n, :s)"),
                {"i": org_id, "n": args.org_name, "s": args.org_slug},
            )
            print(f"  created organisation {org_id} ({args.org_slug})")
        else:
            print(f"  organisation exists {org_id} ({args.org_slug})")

        # Branding: the logo is served by the web app from apps/web/public, so it
        # works offline and is version-controlled alongside the code. OrgBadge
        # falls back to a monogram in `primary_color` if the image ever fails to
        # load, so a missing file degrades instead of breaking the shell.
        await session.execute(
            text("UPDATE organizations SET branding = CAST(:b AS jsonb) WHERE id = :i"),
            {"i": org_id, "b": json.dumps(BRANDING)},
        )
        print(f"  branding set (logo {BRANDING['logo_url']})")

        profile = await session.get(OrgProfile, org_id)
        if profile is None:
            profile = OrgProfile(org_id=org_id)
            session.add(profile)
        profile.categories = PROFILE["categories"]
        profile.weights = PROFILE["weights"]
        profile.value_band_inr = PROFILE["value_band_inr"]
        profile.locations = []
        profile.win_categories = PROFILE["win_categories"]

        # The owner connection BYPASSES row-level security, so this must be
        # filtered by org explicitly — an unfiltered query sees every tenant's
        # facts and would wrongly conclude this org is already seeded.
        existing = (
            await session.execute(
                select(CompanyFact.id).where(CompanyFact.org_id == org_id).limit(1)
            )
        ).first()
        if existing:
            print("  capability data already present — leaving it untouched")
        else:
            for fact in FACTS:
                session.add(CompanyFact(org_id=org_id, verified_at=VERIFIED, **fact))
            for product in PRODUCTS:
                session.add(
                    CatalogueProduct(org_id=org_id, verified_at=VERIFIED, **product)
                )
            print(f"  seeded {len(FACTS)} public facts + {len(PRODUCTS)} products")

        await session.commit()
    await engine.dispose()

    print(f"""
Done. Organisation id for the web app:
  {org_id}

WHAT IS DELIBERATELY MISSING (and why the checker will say needs_human):
  * certificate expiry dates  — not public; attach the certificates
  * product lead times        — not public; from the PIM/SAP export
  * monthly capacity          — not public
  * past order values         — no Godrej contract values are publicly
                                documented, and inventing "similar work
                                experience" would be the exact failure this
                                product exists to prevent
Load these through the onboarding wizard (Company facts / Product catalogue CSV)
once Godrej supplies them — see SPEC §21.
""")


if __name__ == "__main__":
    asyncio.run(main())
