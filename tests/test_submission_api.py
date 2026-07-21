"""US-18 integration: the checklist lists required documents, the system
catches a wrong format and an unsigned file, ticking needs a named human,
and nothing is submit-ready until every required item is ticked."""

import uuid

import pytest

from test_checking_api import client_for, make_app
from test_parser_ladder import DIGITAL
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration


async def uploaded_tender(client):
    response = await client.post(
        "/tenders/upload",
        files={"file": ("tender.pdf", DIGITAL, "application/pdf")},
    )
    return response.json()["tender_id"]


async def test_checklist_lists_required_documents(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    async with client_for(app, org_id) as client:
        tender_id = await uploaded_tender(client)
        checklist = (await client.post(f"/tenders/{tender_id}/checklist")).json()

    names = {i["name"] for i in checklist["items"]}
    assert {"Technical Bid", "Price Bid / BOQ", "Signed bidder declarations"} <= names
    assert checklist["required_count"] >= 4
    assert checklist["submit_ready"] is False    # nothing ticked yet


async def test_wrong_format_is_caught_and_blocks_tick(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    async with client_for(app, org_id) as client:
        tender_id = await uploaded_tender(client)
        items = (await client.post(f"/tenders/{tender_id}/checklist")).json()["items"]
        technical = next(i for i in items if i["name"] == "Technical Bid")

        # attach a .docx where a .pdf is required
        attached = (await client.post(
            f"/checklist/items/{technical['id']}/attach",
            json={"format": "docx", "signed": True},
        )).json()
        assert attached["checks_pass"] is False
        assert "required" in attached["checks_reason"]

        blocked = await client.post(
            f"/checklist/items/{technical['id']}/tick", json={"name": "Priya N"}
        )
        assert blocked.status_code == 409
        assert "format" in blocked.json()["detail"]


async def test_unsigned_document_is_flagged_and_blocks_tick(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    async with client_for(app, org_id) as client:
        tender_id = await uploaded_tender(client)
        items = (await client.post(f"/tenders/{tender_id}/checklist")).json()["items"]
        declarations = next(i for i in items if i["name"] == "Signed bidder declarations")

        attached = (await client.post(
            f"/checklist/items/{declarations['id']}/attach",
            json={"format": "pdf", "signed": False},
        )).json()
        assert attached["checks_pass"] is False
        assert "not signed" in attached["checks_reason"]

        blocked = await client.post(
            f"/checklist/items/{declarations['id']}/tick", json={"name": "Priya N"}
        )
        assert blocked.status_code == 409


async def test_checklist_only_complete_when_every_item_ticked_by_a_human(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    async with client_for(app, org_id) as client:
        tender_id = await uploaded_tender(client)
        checklist = (await client.post(f"/tenders/{tender_id}/checklist")).json()

        # attach a valid, signed file to every item; the system checks pass
        for item in checklist["items"]:
            await client.post(
                f"/checklist/items/{item['id']}/attach",
                json={"format": item["required_format"], "signed": True},
            )

        # not ready until a human ticks — attaching alone does not tick
        mid = (await client.get(f"/tenders/{tender_id}/checklist")).json()
        assert mid["submit_ready"] is False
        assert mid["ticked_count"] == 0

        # ticking needs a named human
        first = mid["items"][0]
        nameless = await client.post(
            f"/checklist/items/{first['id']}/tick", json={"name": ""}
        )
        assert nameless.status_code == 422

        for item in mid["items"]:
            ticked = await client.post(
                f"/checklist/items/{item['id']}/tick", json={"name": "Priya N"}
            )
            assert ticked.status_code == 200

        final = (await client.get(f"/tenders/{tender_id}/checklist")).json()
        assert final["submit_ready"] is True
        assert all(i["ticked_by"] == "Priya N" for i in final["items"])


async def test_checklist_respects_rls(owner_conn, app_engine):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    async with client_for(app, org_a) as client:
        tender_id = await uploaded_tender(client)
        await client.post(f"/tenders/{tender_id}/checklist")

    from sqlalchemy import text

    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_b)},
        )
        count = (
            await conn.execute(text("SELECT count(*) FROM submission_items"))
        ).scalar()
    assert count == 0
