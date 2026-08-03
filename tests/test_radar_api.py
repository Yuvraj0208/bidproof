"""US-02 integration: auto-triage after parse, radar lists, Checkpoint-0
queue + resolution, per-org config weights, RLS."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from test_parser_ladder import DIGITAL
from test_upload_api import create_org

pytestmark = pytest.mark.integration

# digital.pdf talks about industrial storage racks, warehouses, Rs 5 crore
# turnover and Rs 2,50,000 EMD — the profile below matches it on purpose.
PROFILE = {
    "categories": [
        {"name": "storage racks", "keywords": ["storage", "rack", "warehouse"]}
    ],
    "weights": {},
    "value_band_inr": {"min_inr": 10000000, "max_inr": 1000000000},
    "locations": [],
    "win_categories": ["storage racks"],
}


async def seed_profile(owner_conn, org_id, profile=None):
    p = profile or PROFILE
    await owner_conn.execute(
        text(
            "INSERT INTO org_profiles "
            "(org_id, categories, weights, value_band_inr, locations, win_categories) "
            "VALUES (:o, :c, :w, :v, :l, :wc)"
        ),
        {
            "o": org_id,
            "c": json.dumps(p["categories"]),
            "w": json.dumps(p["weights"]),
            "v": json.dumps(p["value_band_inr"]),
            "l": json.dumps(p["locations"]),
            "wc": json.dumps(p["win_categories"]),
        },
    )
    await owner_conn.commit()


def client_for(org_id):
    from app.main import create_app

    return AsyncClient(
        transport=ASGITransport(app=create_app()),
        base_url="http://test",
        headers={"X-Org-Id": str(org_id)},
    )


async def upload_digital(client):
    response = await client.post(
        "/tenders/upload",
        files={"file": ("tender.pdf", DIGITAL, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["tender_id"]


async def test_uploaded_tender_is_auto_triaged_into_lane(owner_conn):
    org_id = await create_org(owner_conn)
    await seed_profile(owner_conn, org_id)

    async with client_for(org_id) as client:
        tender_id = await upload_digital(client)
        cards = (await client.get("/radar", params={"list": "in_our_lane"})).json()

    assert len(cards) == 1
    card = cards[0]
    assert card["tender_id"] == tender_id
    assert card["matched_category"] == "storage racks"
    assert card["fit_score"] > 0.6
    assert card["band"] in ("green", "yellow")
    assert card["confidence"] is not None
    assert any("category 'storage racks'" in r for r in card["reasons"])
    assert any("provisional checks" in r for r in card["reasons"])


async def test_profileless_org_queues_for_human_and_resolves(owner_conn):
    org_id = await create_org(owner_conn)  # no profile: nothing is known

    async with client_for(org_id) as client:
        tender_id = await upload_digital(client)

        queued = (await client.get("/radar", params={"list": "needs_human"})).json()
        assert [c["tender_id"] for c in queued] == [tender_id]
        assert queued[0]["checkpoint0"] == "queued"

        bad = await client.post(
            f"/tenders/{tender_id}/triage/resolve",
            json={"list": "needs_human", "reason": "x"},
        )
        assert bad.status_code == 400

        resolved = await client.post(
            f"/tenders/{tender_id}/triage/resolve",
            json={"list": "in_our_lane", "reason": "known buyer, we bid these"},
        )
        assert resolved.status_code == 200
        assert resolved.json()["checkpoint0"] == "confirmed"

        lane = (await client.get("/radar", params={"list": "in_our_lane"})).json()
        assert [c["tender_id"] for c in lane] == [tender_id]

    assert queued[0]["reasons"], "the queue card must explain itself too"


async def test_weights_are_per_org_config(owner_conn):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    # 'conveyor' is absent from digital.pdf → category scores 2/3, while the
    # value component scores 1.0 — so different weights give different fits.
    partial_match = [
        {"name": "storage racks", "keywords": ["storage", "rack", "conveyor"]}
    ]
    category_heavy = dict(PROFILE, categories=partial_match,
                          weights={"category": 0.8, "eligibility": 0.05,
                                   "value": 0.05, "location": 0.05,
                                   "win_history": 0.05})
    value_heavy = dict(PROFILE, categories=partial_match,
                       weights={"category": 0.05, "eligibility": 0.05,
                                "value": 0.8, "location": 0.05,
                                "win_history": 0.05})
    await seed_profile(owner_conn, org_a, category_heavy)
    await seed_profile(owner_conn, org_b, value_heavy)

    async with client_for(org_a) as client:
        await upload_digital(client)
        fit_a = (await client.get("/radar")).json()[0]["fit_score"]
    async with client_for(org_b) as client:
        await upload_digital(client)
        fit_b = (await client.get("/radar")).json()[0]["fit_score"]

    assert fit_a != fit_b, "fit must follow tenant config, not code"


async def test_radar_respects_rls(owner_conn):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    await seed_profile(owner_conn, org_a)

    async with client_for(org_a) as client:
        await upload_digital(client)
    async with client_for(org_b) as client:
        cards = (await client.get("/radar")).json()

    assert cards == []


async def test_the_deadline_reason_is_recomputed_when_the_card_is_read(owner_conn):
    """The card must explain itself as of today (SPEC section 3.2).

    A CWC tender triaged on 30 July still said "closes in 8 days" on 3 August,
    beside a countdown chip reading "4d left" — one card, two answers. Nothing
    ever corrected it: re-listing a tender already held is a duplicate and
    `_ingest_one` returns early, so the stored sentence just aged.

    Here the stale phrase is written straight into the triage record, which is
    exactly the state that outlived the tender on disk.
    """
    org_id = await create_org(owner_conn)
    await seed_profile(owner_conn, org_id)

    async with client_for(org_id) as client:
        tender_id = await upload_digital(client)

        closing = datetime.now(timezone.utc) + timedelta(days=4, hours=3)
        await owner_conn.execute(
            text(
                "UPDATE tenders SET closing_at = :c, "
                "triage = jsonb_set(triage, '{reasons}', :r::jsonb) WHERE id = :i"
            ),
            {
                "c": closing,
                "r": json.dumps(
                    [
                        "category 'storage racks' matched 25%",
                        "tender value unknown",
                        "closes in 8 days",   # what triage recorded four days ago
                        "won in this category before",
                    ]
                ),
                "i": tender_id,
            },
        )
        await owner_conn.commit()

        card = (await client.get("/radar", params={"list": "in_our_lane"})).json()[0]

    assert "closes in 4 days" in card["reasons"]
    assert "closes in 8 days" not in card["reasons"]
    # Replaced in place; the durable reasons are still the original triage's.
    assert card["reasons"][2] == "closes in 4 days"
    assert card["reasons"][0] == "category 'storage racks' matched 25%"
    assert card["reasons"][3] == "won in this category before"
