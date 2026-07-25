"""US-10 integration: export refuses on an unaddressed mandatory clause or a
contradicted claim; a logged override unblocks; a clean proposal exports."""

import io

import pytest
from openpyxl.utils.exceptions import InvalidFileException  # noqa: F401 (zip check)
from sqlalchemy import text

from test_checking_api import client_for, make_app, seed_and_upload
from test_parser_ladder import DIGITAL
from test_rules_api import FakeGateway
from test_section_approval_api import ContradictingWriter
from test_upload_api import create_org

pytestmark = pytest.mark.integration

DOCX_ZIP_MAGIC = b"PK\x03\x04"


async def go_and_draft(client):
    tender_id = await seed_and_upload(client)
    await client.post(f"/tenders/{tender_id}/extract")
    await client.post(f"/tenders/{tender_id}/check")
    await client.post(f"/tenders/{tender_id}/decide", json={"tender_value_inr": 5e7})
    await client.post(f"/tenders/{tender_id}/proposal")
    return tender_id


async def test_export_refuses_on_unaddressed_mandatory_clause(owner_conn):
    # No capability data → min_turnover (eligibility) is unaddressed.
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        response = await client.post(
            "/tenders/upload",
            files={"file": ("tender.pdf", DIGITAL, "application/pdf")},
        )
        tender_id = response.json()["tender_id"]
        await client.post(f"/tenders/{tender_id}/extract")
        await client.post(f"/tenders/{tender_id}/check")

        preflight = (
            await client.get(f"/tenders/{tender_id}/proposal/export/preflight")
        ).json()
        assert preflight["can_export"] is False
        assert any(
            b["type"] == "unaddressed_mandatory_clause" for b in preflight["blockers"]
        )

        refused = await client.post(f"/tenders/{tender_id}/proposal/export")
        assert refused.status_code == 409
        detail = refused.json()["detail"]
        assert any(
            b["type"] == "unaddressed_mandatory_clause" for b in detail["blockers"]
        )


async def test_export_refuses_on_contradicted_claim(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(ContradictingWriter(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        tender_id = await go_and_draft(client)   # capability satisfies eligibility
        preflight = (
            await client.get(f"/tenders/{tender_id}/proposal/export/preflight")
        ).json()

    assert preflight["can_export"] is False
    assert any(b["type"] == "contradicted_claim" for b in preflight["blockers"])


async def test_logged_override_unblocks_and_produces_a_document(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(ContradictingWriter(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        tender_id = await go_and_draft(client)

        # override needs both a name and a written reason
        bad = await client.post(
            f"/tenders/{tender_id}/proposal/export",
            json={"override_name": "Bid Head", "override_reason": "ok"},
        )
        assert bad.status_code == 400

        ok = await client.post(
            f"/tenders/{tender_id}/proposal/export",
            json={"override_name": "Bid Head",
                  "override_reason": "client confirmed the figure by email"},
        )
        assert ok.status_code == 200
        assert ok.headers["content-type"].endswith("wordprocessingml.document")
        assert ok.headers["x-export-overridden"] == "true"
        assert ok.content[:4] == DOCX_ZIP_MAGIC       # a real .docx (zip)

    # the override is recorded in the append-only audit log
    row = (
        await owner_conn.execute(
            text("SELECT actor, details FROM audit_log WHERE action = 'export_override'")
        )
    ).one()
    assert row.actor == "Bid Head"
    assert row.details["reason"] == "client confirmed the figure by email"
    assert "contradicted_claim" in row.details["blockers"]


async def test_clean_proposal_exports_without_override(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        tender_id = await go_and_draft(client)   # all comply, all verified

        preflight = (
            await client.get(f"/tenders/{tender_id}/proposal/export/preflight")
        ).json()
        assert preflight["can_export"] is True

        exported = await client.post(f"/tenders/{tender_id}/proposal/export")
        assert exported.status_code == 200
        assert exported.headers["x-export-overridden"] == "false"
        assert exported.content[:4] == DOCX_ZIP_MAGIC

    # the document opens and carries the compliance matrix
    from docx import Document as Docx

    doc = Docx(io.BytesIO(exported.content))
    headings = [p.text for p in doc.paragraphs]
    assert any("Compliance Matrix" in h for h in headings)


async def test_override_is_append_only(owner_conn, app_engine):
    org_id = await create_org(owner_conn)
    app = make_app(ContradictingWriter(['{"rules": []}']))
    async with client_for(app, org_id) as client:
        tender_id = await go_and_draft(client)
        await client.post(
            f"/tenders/{tender_id}/proposal/export",
            json={"override_name": "Bid Head", "override_reason": "reviewed and accepted"},
        )

    from sqlalchemy.exc import DBAPIError, ProgrammingError

    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_id)},
        )
        with pytest.raises((ProgrammingError, DBAPIError)):
            await conn.execute(
                text("UPDATE audit_log SET details = '{}' WHERE action = 'export_override'")
            )
