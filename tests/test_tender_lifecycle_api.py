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
from test_parser_ladder import DIGITAL, MIXED
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


async def test_bulk_delete_clears_a_selection_and_audits_every_one(owner_conn):
    """Portal discovery brings in more noise than anyone dismisses one at a time.

    The batch must keep every guarantee the single delete has: gated to
    bid_head-or-above, and an audit row per tender that outlives it.
    """
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))

    async with client_for(app, org_id) as client:
        first = await _upload(client)
        # A second distinct document, so it is not rejected as a duplicate.
        second = (
            await client.post(
                "/tenders/upload",
                files={"file": ("other.pdf", MIXED, "application/pdf")},
            )
        ).json()["tender_id"]

        refused = await client.post(
            "/tenders/bulk-delete",
            json={"tender_ids": [first, second]},
            headers={"X-Role": "bid_executive"},
        )
        assert refused.status_code == 403, "deleting is not an executive's call"

        ghost = "00000000-0000-0000-0000-000000000009"
        result = await client.post(
            "/tenders/bulk-delete",
            json={"tender_ids": [first, second, ghost]},
            headers={"X-Role": "bid_head"},
        )
        assert result.status_code == 200, result.text
        body = result.json()
        assert sorted(body["deleted"]) == sorted([first, second])
        # An id that no longer exists is reported, not fatal — a stale tab must
        # not be able to fail the whole action.
        assert body["not_found"] == [ghost]

        assert (await client.get(f"/tenders/{first}")).status_code == 404
        assert (await client.get(f"/tenders/{second}")).status_code == 404

    for tender_id in (first, second):
        actions = (
            await owner_conn.execute(
                text("SELECT action FROM audit_log WHERE tender_id = :t"),
                {"t": tender_id},
            )
        ).scalars().all()
        assert "tender_deleted" in actions, f"no audit row for {tender_id}"


async def test_bulk_delete_rejects_an_empty_selection(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    async with client_for(app, org_id) as client:
        empty = await client.post(
            "/tenders/bulk-delete",
            json={"tender_ids": []},
            headers={"X-Role": "bid_head"},
        )
    assert empty.status_code == 422


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
