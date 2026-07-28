"""Show everything BidProof knows about one company, and where it came from.

This is the capability database the Matcher checks every tender rule against. If
a verdict says "no candidate products" or "needs a human", the answer to *why* is
almost always here — something is missing, not broken.

    python -m uv run --project apps/api python tools/show_company.py
    python -m uv run --project apps/api python tools/show_company.py --company godrej
    python -m uv run --project apps/api python tools/show_company.py --gaps

Read-only: it opens the database, prints, and closes. Safe to run mid-demo.
"""

import argparse
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Windows consoles are cp1252 and this data contains ₹ and Devanagari.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.core.config import get_settings  # noqa: E402


def missing(value) -> bool:
    """Whether we genuinely do not know this.

    NOT just `is None`: an empty dict or blank string is equally unknown, and
    counting only NULLs made the gap report contradict its own listing —
    `price_band_inr` is stored as `{}`, which printed UNKNOWN yet counted as
    present.
    """
    if value is None:
        return True
    if isinstance(value, (dict, list, str)) and len(value) == 0:
        return True
    return False


def show(label: str, value) -> None:
    print(f"  {label:<26} {'UNKNOWN' if missing(value) else value}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--company", default="", help="match on name (default: list all)")
    parser.add_argument(
        "--gaps", action="store_true",
        help="only what is MISSING — the fields that force 'needs human'")
    args = parser.parse_args()

    # The owner engine, because this reads across tenants deliberately; the app
    # role is blocked from that by row-level security, which is the point.
    engine = create_async_engine(get_settings().database_url_owner)
    try:
        async with engine.connect() as conn:
            orgs = (
                await conn.execute(
                    text(
                        "SELECT id, name, slug FROM organizations "
                        "WHERE :q = '' OR lower(name) LIKE '%' || lower(:q) || '%' "
                        "ORDER BY name"
                    ),
                    {"q": args.company},
                )
            ).all()
            if not orgs:
                print(f"no company matches {args.company!r}")
                return 1

            for org_id, name, slug in orgs:
                print("=" * 74)
                print(f"{name}   ({slug})")
                print("=" * 74)

                profile = (
                    await conn.execute(
                        text(
                            "SELECT categories, value_band_inr, locations, "
                            "win_categories FROM org_profiles WHERE org_id = :o"
                        ),
                        {"o": org_id},
                    )
                ).first()
                if not args.gaps:
                    print("\nWHAT WE BID ON (drives the radar's fit score)")
                    if profile is None:
                        print("  (no radar profile — every tender scores blind)")
                    else:
                        categories, band, locations, wins = profile
                        show("categories", categories)
                        show("value band (₹)", band)
                        show("locations", locations)
                        show("won before in", wins)

                facts = (
                    await conn.execute(
                        text(
                            "SELECT fact_type, legal_entity, fiscal_year, value_text, "
                            "value_number, unit, valid_until, source "
                            "FROM company_facts WHERE org_id = :o "
                            "ORDER BY fact_type, fiscal_year DESC NULLS LAST"
                        ),
                        {"o": org_id},
                    )
                ).all()
                if not args.gaps:
                    print(f"\nCOMPANY FACTS — {len(facts)}")
                    print("  Every one carries its own source. A fact with no")
                    print("  source is not evidence; the checker will not spend it.")
                    for f in facts:
                        kind, entity, year, vtext, vnum, unit, until, source = f
                        value = vtext or (
                            f"{vnum:,.2f} {unit or ''}".strip()
                            if vnum is not None
                            else None
                        )
                        print(f"\n  • {kind}  {('FY' + year) if year else ''}")
                        show("value", value)
                        if entity:
                            show("legal entity", entity)
                        if until:
                            show("valid until", until)
                        show("source", (source or "")[:80])

                products = (
                    await conn.execute(
                        text(
                            "SELECT product_name, category, standards, lead_time_days, "
                            "capacity_per_month, plant, price_band_inr "
                            "FROM product_catalogue WHERE org_id = :o "
                            "ORDER BY category, product_name"
                        ),
                        {"o": org_id},
                    )
                ).all()
                if not args.gaps:
                    print(f"\n\nPRODUCT CATALOGUE — {len(products)}")
                    print("  What the Matcher offers against a technical requirement.")
                    for p in products:
                        pname, category, standards, lead, capacity, plant, price = p
                        print(f"\n  • {pname}   [{category}]")
                        show("standards", standards)
                        show("lead time (days)", lead)
                        show("capacity / month", capacity)
                        show("plant", plant)
                        show("price band (₹)", price)

                # ---- What is missing, and what it costs ---------------------
                no_standards = [p for p in products if missing(p[2])]
                no_lead = [p for p in products if missing(p[3])]
                no_capacity = [p for p in products if missing(p[4])]
                no_plant = [p for p in products if missing(p[5])]
                no_price = [p for p in products if missing(p[6])]
                undated = [f for f in facts if missing(f[6])]

                print("\n\nGAPS — why a rule ends up at 'needs human'")
                print("  The system abstains rather than guessing (SPEC §9 rule 3),")
                print("  so each gap below is a verdict a person has to make by hand.")
                show("no standards listed", f"{len(no_standards)} of {len(products)}")
                show("no lead time", f"{len(no_lead)} of {len(products)}")
                show("…no monthly capacity", f"{len(no_capacity)} of {len(products)}")
                show("…no plant named", f"{len(no_plant)} of {len(products)}")
                show("…no price band", f"{len(no_price)} of {len(products)}")
                show("facts with no expiry date", f"{len(undated)} of {len(facts)}")
                if no_lead:
                    print("\n  Delivery-schedule rules cannot be answered without lead")
                    print("  times. That is the single highest-value thing to fill in.")
                print()
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
