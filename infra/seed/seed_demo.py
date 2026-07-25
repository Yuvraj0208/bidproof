"""One-command demo reset (Task 6).

    python -m uv run --project apps/api python infra/seed/seed_demo.py

Idempotent: safe to run repeatedly, and the thing to run after an integration
test wipes the database (the `owner_conn` fixture TRUNCATEs organizations).

It creates:
  * the demo organisation + its radar profile (so triage can lane a tender);
  * the capability database and product catalogue;
  * the past-proposal library;
  * two tender PDFs and, if the API is up, pushes them through the real
    pipeline so every screen is alive when opened cold.

The second tender matters: **the company genuinely FAILS it** (₹500 crore
turnover, ISO 45001, 15-day delivery). Without a failing requirement there are
no `gap` verdicts, and with no gaps the QuestionWriter drafts nothing — the
pre-bid-query half of the demo spine is invisible. See docs/FINISH_STATUS.md.

Pass --no-pipeline to seed data only and skip every model call.
"""

import argparse
import asyncio
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "infra" / "seed"))

OWNER = "postgresql+asyncpg://bidproof_owner:bidproof_dev@localhost:5433/bidproof"
API = "http://localhost:8000"
SLUG = "demo-org"
ORG_NAME = "Demo Storage Co"

# What the company bids for — without this the radar cannot lane anything.
PROFILE = {
    "categories": [
        {"name": "storage racks",
         "keywords": ["storage", "rack", "racking", "shelving", "pallet", "warehouse"]},
        {"name": "mezzanine systems",
         "keywords": ["mezzanine", "platform", "structural", "steel structure"]},
        {"name": "material handling",
         "keywords": ["material handling", "trolley", "equipment", "fabrication"]},
    ],
    "weights": {"category_fit": 0.4, "value_band": 0.3, "past_wins": 0.3},
    "value_band_inr": {"min_inr": 100_000, "max_inr": 5_000_000_000},
    "win_categories": ["storage racks", "mezzanine systems"],
}

WINNABLE = """Section 1: Eligibility
TENDER NOTICE No. 42/2026
Supply of industrial storage racks to the Central Warehouse.
Earnest Money Deposit: Rs 2,50,000 payable at submission.
Minimum average annual turnover: Rs 5 crore over last 3 FY.
Delivery period: 90 days from purchase order date.
Bidder must hold valid ISO 9001 certification.
Pre-bid queries close 14 days before the submission deadline.
Performance bank guarantee: 5 percent of contract value."""

# Deliberately out of reach: this is the tender that PRODUCES GAPS, which is
# what makes pre-bid query letters (US-08) demonstrable at all.
HARD = """Section 1: Eligibility
TENDER NOTICE No. 88/2026
Supply and installation of automated storage and retrieval systems.
Earnest Money Deposit: Rs 25,00,000 payable at submission.
Minimum average annual turnover: Rs 500 crore over last 3 FY.
Delivery period: 15 days from purchase order date.
Bidder must hold valid ISO 45001 certification.
Bidder must hold valid ISO 9001 certification.
Pre-bid queries close 7 days before the submission deadline.
Performance bank guarantee: 10 percent of contract value."""


def make_pdf(text_body: str, path: Path) -> None:
    """A two-page digital PDF, same shape as the test fixtures.

    The generated files are committed, so a normal reset needs nothing extra;
    reportlab is only required to REGENERATE them (delete a file to force it).
    """
    if path.exists():
        return
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        raise SystemExit(
            f"{path.name} is missing and reportlab is not installed.\n"
            "Either restore the committed fixture, or install the generator:\n"
            "  python -m uv pip install --python apps/api/.venv reportlab"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=letter)
    for page, heading in enumerate(("Section 1: Eligibility", "Section 2: Commercial Terms")):
        y = 720
        for line in text_body.splitlines():
            pdf.setFont("Helvetica-Bold" if line.startswith("Section") else "Helvetica", 11)
            pdf.drawString(72, y, heading if line.startswith("Section") else line)
            y -= 16
        pdf.showPage()
    pdf.save()


async def seed_database() -> uuid.UUID:
    from seed_capability_demo import FACTS, PRODUCTS, SRC_FACTS, SRC_PRODUCTS, VERIFIED

    from app.models import CatalogueProduct, CompanyFact, OrgProfile

    engine = create_async_engine(OWNER)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        org_id = (
            await session.execute(
                text("SELECT id FROM organizations WHERE slug = :s"), {"s": SLUG}
            )
        ).scalar()
        if org_id is None:
            org_id = uuid.uuid4()
            await session.execute(
                text("INSERT INTO organizations (id, name, slug) VALUES (:i, :n, :s)"),
                {"i": org_id, "n": ORG_NAME, "s": SLUG},
            )
            print(f"  created organisation {org_id}")
        else:
            print(f"  organisation exists {org_id}")

        profile = await session.get(OrgProfile, org_id)
        if profile is None:
            profile = OrgProfile(org_id=org_id)
            session.add(profile)
        profile.categories = PROFILE["categories"]
        profile.weights = PROFILE["weights"]
        profile.value_band_inr = PROFILE["value_band_inr"]
        profile.locations = []
        profile.win_categories = PROFILE["win_categories"]

        have_facts = (
            await session.execute(select(CompanyFact.id).limit(1))
        ).first()
        if not have_facts:
            for fact in FACTS:
                session.add(CompanyFact(org_id=org_id, source=SRC_FACTS,
                                        verified_at=VERIFIED, **fact))
            for product in PRODUCTS:
                session.add(CatalogueProduct(org_id=org_id, source=SRC_PRODUCTS,
                                             verified_at=VERIFIED, **product))
            print(f"  seeded {len(FACTS)} facts + {len(PRODUCTS)} products")
        else:
            print("  capability data already present")

        await session.commit()
    await engine.dispose()
    return org_id


async def seed_library(org_id: uuid.UUID) -> None:
    import seed_library_demo

    try:
        await seed_library_demo.main()
    except SystemExit:
        pass
    except Exception as exc:  # pragma: no cover - best effort
        print(f"  library seed skipped: {exc}")


def _body(response) -> dict:
    """Endpoints can return an error page; never let that mask the real cause."""
    try:
        return response.json()
    except Exception:
        return {"_status": response.status_code, "_text": response.text[:160]}


async def run_pipeline(org_id: uuid.UUID, pdfs: list[tuple[str, Path]]) -> None:
    """Push each tender through the real endpoints, exactly as a user would."""
    headers = {"X-Org-Id": str(org_id), "X-Role": "admin"}
    async with httpx.AsyncClient(base_url=API, timeout=900, headers=headers) as client:
        try:
            await client.get("/health", timeout=5)
        except Exception:
            print("  API not reachable — skipping the pipeline "
                  "(start it, then re-run, or pass --no-pipeline)")
            return

        for label, path in pdfs:
            files = {"file": (path.name, path.read_bytes(), "application/pdf")}
            response = await client.post("/tenders/upload", files=files)
            if response.status_code == 409:
                print(f"  {label}: already uploaded")
                continue
            if response.status_code != 201:
                print(f"  {label}: upload failed {response.status_code}")
                continue
            tender_id = response.json()["tender_id"]
            print(f"  {label}: uploaded {tender_id}")

            # Parsing runs in the background; wait for elements before extracting.
            for _ in range(60):
                elements = await client.get(f"/tenders/{tender_id}/elements")
                if elements.status_code == 200 and elements.json():
                    break
                await asyncio.sleep(2)

            extracted = _body(await client.post(f"/tenders/{tender_id}/extract"))
            checked = _body(await client.post(f"/tenders/{tender_id}/check"))
            print(f"     rules={extracted.get('rules', extracted)} "
                  f"verdicts={checked.get('verdicts', checked)}")

            await client.post(f"/tenders/{tender_id}/decide",
                              json={"tender_value_inr": 8_000_000})
            questions = _body(await client.post(f"/tenders/{tender_id}/questions"))
            print(f"     pre-bid letters drafted: {questions.get('letters', questions)}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-pipeline", action="store_true",
                        help="seed data only; make no model calls")
    args = parser.parse_args()

    print("BidProof demo reset")
    org_id = await seed_database()
    await seed_library(org_id)

    fixtures = REPO / "infra" / "seed" / "fixtures"
    winnable = fixtures / "tender_winnable.pdf"
    hard = fixtures / "tender_hard.pdf"
    make_pdf(WINNABLE, winnable)
    make_pdf(HARD, hard)
    print(f"  wrote {winnable.name} and {hard.name}")

    if not args.no_pipeline:
        await run_pipeline(org_id, [("winnable tender", winnable),
                                    ("hard tender (produces gaps)", hard)])

    print(f"\nDone. Paste this organisation id into the web app:\n  {org_id}\n")


if __name__ == "__main__":
    asyncio.run(main())
