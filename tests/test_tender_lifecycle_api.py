"""Human control over cost and clutter (FINISH_STATUS R1, R2).

Two promises:
  * uploading a tender must NOT send it to a model — a named human opts that
    specific tender in via /process, so portal noise never costs money;
  * a human can delete a tender, but only bid_head-or-above, and the deletion
    is written to the append-only audit log.
"""

import pytest
from sqlalchemy import text

from test_checking_api import client_for, make_app
from test_parser_ladder import DIGITAL
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration


async def _upload(client):
    response = await client.post(
        "/tenders/upload", files={"file": ("t.pdf", DIGITAL, "application/pdf")}
    )
    assert response.status_code == 201, response.text
    return response.json()["tender_id"]


async def test_upload_alone_never_reaches_a_model(owner_conn):
    org_id = await create_org(owner_conn)
    gateway = FakeGateway(['{"rules": []}'])
    app = make_app(gateway)

    async with client_for(app, org_id) as client:
        tender_id = await _upload(client)
        rules = (await client.get(f"/tenders/{tender_id}/rules")).json()

    # Parsing and triage may run; extraction must not have been attempted.
    assert rules == []
    assert gateway.calls == [], "upload must not call a model — cost is opt-in"


async def test_process_is_the_opt_in_that_extracts_and_checks(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))

    async with client_for(app, org_id) as client:
        tender_id = await _upload(client)
        processed = await client.post(f"/tenders/{tender_id}/process")
        assert processed.status_code == 200, processed.text
        body = processed.json()
        assert body["rules"] > 0
        rules = (await client.get(f"/tenders/{tender_id}/rules")).json()
        assert len(rules) == body["rules"]

    # The opt-in is attributable.
    actions = (
        await owner_conn.execute(
            text("SELECT action FROM audit_log WHERE tender_id = :t"),
            {"t": tender_id},
        )
    ).scalars().all()
    assert "tender_processed_with_ai" in actions


async def test_delete_requires_bid_head_and_is_audited(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))

    async with client_for(app, org_id) as client:
        tender_id = await _upload(client)

        refused = await client.delete(
            f"/tenders/{tender_id}", headers={"X-Role": "bid_executive"}
        )
        assert refused.status_code == 403, "deleting is not an executive's call"

        deleted = await client.delete(
            f"/tenders/{tender_id}", headers={"X-Role": "bid_head"}
        )
        assert deleted.status_code == 200
        assert (await client.get(f"/tenders/{tender_id}")).status_code == 404

    # The audit row outlives the tender it describes.
    actions = (
        await owner_conn.execute(
            text("SELECT action FROM audit_log WHERE tender_id = :t"),
            {"t": tender_id},
        )
    ).scalars().all()
    assert "tender_deleted" in actions


async def test_processing_a_metadata_only_tender_explains_itself(owner_conn):
    """Portal-discovered tenders often have no PDF; say so instead of 500ing."""
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))

    tender_id = (
        await owner_conn.execute(
            text("INSERT INTO tenders (org_id, title, source) "
                 "VALUES (:o, 'metadata only', 'cppp') RETURNING id"),
            {"o": org_id},
        )
    ).scalar()
    await owner_conn.commit()

    async with client_for(app, org_id) as client:
        response = await client.post(f"/tenders/{tender_id}/process")

    assert response.status_code == 409
    assert "no parsed document" in response.json()["detail"]
