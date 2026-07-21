"""US-20 — the correction flywheel across tenders.

Acceptance criteria (SPEC §3.2, §8 layer 4, §11.3):
  1. Correcting the same clause type twice → the third similar tender is
     pre-filled that way, with a VISIBLE provenance note.
  2. Only reviewer-or-above corrections become labels; a junior correction
     never teaches the system (the poisoning defence).
"""

import pytest

from app.core.db import org_scoped_session
from app.core.roles import Role
from app.models import Tender
from app.services import flywheel
from test_checking_api import client_for, make_app, seed_and_upload
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration

CORR = "consortium allowed with a lead partner holding at least 51%"


async def _extract_one_tender(client):
    """A real uploaded + extracted tender, returning (tender_id, rules)."""
    tender_id = await seed_and_upload(client)
    assert (await client.post(f"/tenders/{tender_id}/extract")).status_code == 200
    rules = (await client.get(f"/tenders/{tender_id}/rules")).json()
    assert rules, "extraction should yield at least one grounded rule"
    return tender_id, rules


async def _seed_past_correction(org_id, external_id, key, value, role, name):
    """A past tender where someone corrected clause `key` to `value`. Each runs
    in its own transaction so the created_at timestamps are strictly ordered."""
    async with org_scoped_session(org_id) as session:
        past = Tender(org_id=org_id, title=f"Past tender {external_id}",
                      source="gem", external_id=external_id)
        session.add(past)
        await session.flush()
        await flywheel.record_correction(
            session, org_id=org_id, tender_id=past.id, key=key,
            family="eligibility", corrected_value=value, role=role, name=name,
        )


async def test_third_similar_tender_prefills_with_visible_note(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id, rules = await _extract_one_tender(client)
        key = rules[0]["key"]
        assert rules[0]["learned"] is None  # nothing learned yet

    # Two reviewer-or-above corrections of the SAME clause, the SAME way.
    await _seed_past_correction(org_id, "GEM-1042", key, CORR,
                                Role.REVIEWER, "Priya N")
    await _seed_past_correction(org_id, "GEM-1099", key, CORR,
                                Role.BID_HEAD, "Anil K")

    async with client_for(app, org_id) as client:
        rules_now = (await client.get(f"/tenders/{tender_id}/rules")).json()

    learned = {r["key"]: r["learned"] for r in rules_now}[key]
    assert learned is not None, "the third tender should be pre-filled"
    assert learned["suggested_value"] == CORR
    assert learned["based_on_count"] == 2
    # visible provenance, citing the most recent source tender
    assert learned["note"] == "Based on your correction on Tender #GEM-1099"


async def test_two_junior_corrections_never_prefill(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id, rules = await _extract_one_tender(client)
        key = rules[0]["key"]

    # Two bid_executive (junior) corrections — recorded, but never labels.
    await _seed_past_correction(org_id, "GEM-2042", key, CORR,
                                Role.BID_EXECUTIVE, "Junior A")
    await _seed_past_correction(org_id, "GEM-2099", key, CORR,
                                Role.BID_EXECUTIVE, "Junior B")

    async with client_for(app, org_id) as client:
        rules_now = (await client.get(f"/tenders/{tender_id}/rules")).json()

    learned = {r["key"]: r["learned"] for r in rules_now}[key]
    assert learned is None, "junior corrections must never teach the system"


async def test_correct_endpoint_labels_only_reviewer_and_above(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_id) as client:  # client default role: admin
        tender_id, rules = await _extract_one_tender(client)
        rule_id = rules[0]["rule_id"]
        url = f"/tenders/{tender_id}/rules/{rule_id}/correct"

        junior = await client.post(url, json={"corrected_value": "aaa", "name": "J"},
                                   headers={"X-Role": "bid_executive"})
        assert junior.status_code == 200
        assert junior.json()["is_label"] is False  # recorded, not a label

        reviewer = await client.post(url, json={"corrected_value": "bbb", "name": "Priya"},
                                     headers={"X-Role": "reviewer"})
        assert reviewer.status_code == 200
        assert reviewer.json()["is_label"] is True  # reviewer teaches the system

        blocked = await client.post(url, json={"corrected_value": "ccc", "name": "V"},
                                    headers={"X-Role": "viewer"})
        assert blocked.status_code == 403  # a viewer may not correct at all
