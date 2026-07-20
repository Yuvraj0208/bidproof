"""US-07 integration: a planted corrigendum is detected, only affected rules
re-run, and the EV delta is correct and cited."""

from pathlib import Path

import pytest
from sqlalchemy import text

from test_checking_api import client_for, make_app, seed_and_upload
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration

CORRIGENDUM = (Path(__file__).parent / "fixtures" / "corrigendum.pdf").read_bytes()


async def prepared_tender(client):
    tender_id = await seed_and_upload(client)
    await client.post(f"/tenders/{tender_id}/check")
    await client.post(f"/tenders/{tender_id}/decide", json={"tender_value_inr": 5e7})
    return tender_id


async def test_corrigendum_detected_diffed_and_ev_recomputed(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}', '{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id = await prepared_tender(client)
        rules_before = (await client.get(f"/tenders/{tender_id}/rules")).json()
        delivery_before = next(r for r in rules_before if r["key"] == "delivery_days")

        result = (await client.post(
            f"/tenders/{tender_id}/amend",
            files={"file": ("corrigendum.pdf", CORRIGENDUM, "application/pdf")},
        )).json()

    # The diff names exactly what changed, with the corrigendum page cited.
    changed = {c["key"]: c for c in result["changes"]}
    assert changed["delivery_days"]["old_value"] == "90"
    assert changed["delivery_days"]["new_value"] == "30"
    assert changed["delivery_days"]["page"] == 1
    assert changed["pbg_percent"]["old_value"] == "5"
    assert changed["pbg_percent"]["new_value"] == "10"

    # Only the affected rules were re-checked — not all 12.
    assert result["rules_rechecked"] == 2
    assert set(result["rules_affected"]) == {"delivery_days", "pbg_percent"}

    # Delivery broke: it complied at 90 days, fails at 30 (< our 45-day lead).
    assert "delivery_days" in result["rules_broken"]

    # EV recomputed by plain arithmetic: PBG 5%→10% locks more capital.
    assert result["ev_before_inr"] == 1_155_000.0
    assert result["ev_after_inr"] == 1_005_000.0

    # The alert names the change, the break, and the new EV.
    assert "delivery_days 90→30" in result["message"]
    assert "Breaks delivery_days" in result["message"]
    assert "₹11.55L → ₹10.05L" in result["message"]

    # The changed rule was re-grounded to the corrigendum (a new document).
    assert delivery_before["document_id"]


async def test_only_affected_verdicts_changed(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}', '{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id = await prepared_tender(client)
        before = {v["key"]: v["verdict"]
                  for v in (await client.get(f"/tenders/{tender_id}/verdicts")).json()}
        await client.post(
            f"/tenders/{tender_id}/amend",
            files={"file": ("corrigendum.pdf", CORRIGENDUM, "application/pdf")},
        )
        after = {v["key"]: v["verdict"]
                 for v in (await client.get(f"/tenders/{tender_id}/verdicts")).json()}

    assert before["delivery_days"] == "complies"
    assert after["delivery_days"] == "gap"
    # Untouched rules keep their verdicts.
    assert before["min_turnover"] == after["min_turnover"] == "complies"
    assert before["required_standard"] == after["required_standard"]


async def test_amendment_grounds_changed_rule_to_corrigendum(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}', '{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id = await prepared_tender(client)
        original = next(
            r for r in (await client.get(f"/tenders/{tender_id}/rules")).json()
            if r["key"] == "delivery_days"
        )
        await client.post(
            f"/tenders/{tender_id}/amend",
            files={"file": ("corrigendum.pdf", CORRIGENDUM, "application/pdf")},
        )
        amended = next(
            r for r in (await client.get(f"/tenders/{tender_id}/rules")).json()
            if r["key"] == "delivery_days"
        )
        # its proof now points at a different document (the corrigendum)
        assert amended["document_id"] != original["document_id"]
        assert amended["value"] == "30"

        # and that corrigendum document is streamable for click-to-proof
        pdf = await client.get(f"/documents/{amended['document_id']}/file")
        assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"


async def test_amendments_list_and_rls(owner_conn, app_engine):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}', '{"rules": []}']))

    async with client_for(app, org_a) as client:
        tender_id = await prepared_tender(client)
        await client.post(
            f"/tenders/{tender_id}/amend",
            files={"file": ("corrigendum.pdf", CORRIGENDUM, "application/pdf")},
        )
        listed = (await client.get(f"/tenders/{tender_id}/amendments")).json()
    assert len(listed) == 1
    assert "delivery_days" in listed[0]["message"]

    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_b)},
        )
        count = (await conn.execute(text("SELECT count(*) FROM amendments"))).scalar()
    assert count == 0


async def test_existing_endpoints_survive_a_second_document(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}', '{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id = await prepared_tender(client)
        await client.post(
            f"/tenders/{tender_id}/amend",
            files={"file": ("corrigendum.pdf", CORRIGENDUM, "application/pdf")},
        )
        # the single-document endpoints must not choke on two documents
        detail = await client.get(f"/tenders/{tender_id}")
        elements = await client.get(f"/tenders/{tender_id}/elements")
        document = await client.get(f"/tenders/{tender_id}/document")

    assert detail.status_code == 200
    assert elements.status_code == 200
    assert document.status_code == 200
