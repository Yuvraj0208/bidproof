"""US-03: manual upload endpoint — guardrails, end-to-end pipeline, RLS,
data-layer grounding, and the parse-run log with cost."""

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from test_parser_ladder import DIGITAL, SCANNED, FakeOcr

FIXTURES = Path(__file__).parent / "fixtures"


def make_app(ladder=None, logger=None):
    from app.main import create_app
    from app.observability import get_parse_logger
    from app.parsing import get_ladder

    app = create_app()
    if ladder is not None:
        app.dependency_overrides[get_ladder] = lambda: ladder
    if logger is not None:
        app.dependency_overrides[get_parse_logger] = lambda: logger
    return app


def client_for(app, org_id=None):
    headers = {"X-Org-Id": str(org_id)} if org_id else {}
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=headers
    )


async def create_org(owner_conn):
    org_id = uuid.uuid4()
    await owner_conn.execute(
        text("INSERT INTO organizations (id, name, slug) VALUES (:id, :n, :s)"),
        {"id": org_id, "n": f"Org {org_id.hex[:6]}", "s": f"org-{org_id.hex[:6]}"},
    )
    await owner_conn.commit()
    return org_id


async def upload(client, pdf_bytes, filename="tender.pdf"):
    return await client.post(
        "/tenders/upload",
        files={"file": (filename, pdf_bytes, "application/pdf")},
    )


class CaptureLogger:
    def __init__(self):
        self.entries = []

    def log(self, entry):
        self.entries.append(entry)


# --- Input guardrails (SPEC §10) — no DB needed ----------------------------


async def test_upload_rejects_non_pdf():
    async with client_for(make_app(), org_id=uuid.uuid4()) as client:
        response = await upload(client, b"MZ this is not a pdf", "evil.pdf")
    assert response.status_code == 415


async def test_upload_rejects_oversized_file(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    async with client_for(make_app(), org_id=uuid.uuid4()) as client:
        response = await upload(client, DIGITAL)
    assert response.status_code == 413


async def test_upload_requires_org_context():
    async with client_for(make_app()) as client:
        response = await upload(client, DIGITAL)
    assert response.status_code == 400


# --- End to end (integration: Postgres + MinIO) ----------------------------


@pytest.mark.integration
async def test_upload_with_a_vanished_org_says_so_instead_of_500ing(owner_conn):
    """A browser can hold a signed-in org id after that row has gone — most
    easily by running the integration suite, whose fixtures TRUNCATE
    `organizations`.

    That used to reach the insert and die on a foreign key. The resulting 500
    carries no CORS header (Starlette's ServerErrorMiddleware sits outside the
    CORS middleware), so the browser reported only "TypeError: Failed to fetch"
    and every diagnosis went looking for a network fault.
    """
    import uuid as _uuid

    from test_checking_api import client_for, make_app
    from test_rules_api import FakeGateway

    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))

    async with client_for(app, org_id) as client:
        response = await client.post(
            "/tenders/upload",
            files={"file": ("t.pdf", DIGITAL, "application/pdf")},
            headers={"X-Org-Id": str(_uuid.uuid4())},  # valid UUID, no such org
        )

    assert response.status_code == 404, response.text
    detail = response.json()["detail"]
    assert "no longer exists" in detail
    # It must tell the operator what to DO, not merely that something broke.
    assert "sign in again" in detail


@pytest.mark.integration
async def test_upload_born_digital_end_to_end(owner_conn):
    org_id = await create_org(owner_conn)
    logger = CaptureLogger()
    app = make_app(logger=logger)

    async with client_for(app, org_id=org_id) as client:
        response = await upload(client, DIGITAL)
        assert response.status_code == 201, response.text
        body = response.json()
        tender_id = body["tender_id"]

        detail = (await client.get(f"/tenders/{tender_id}")).json()
        assert detail["parse"]["status"] == "succeeded"
        assert detail["parse"]["pages_total"] == 2
        assert detail["parse"]["pages_text"] == 2
        assert detail["parse"]["pages_flagged"] == 0

        elements = (
            await client.get(f"/tenders/{tender_id}/elements", params={"page_no": 1})
        ).json()

    assert elements, "born-digital parse must yield grounded elements"
    for el in elements:
        assert el["el_id"]
        assert el["page_no"] == 1
        assert el["bbox"]["x1"] > el["bbox"]["x0"]
        assert el["bbox"]["y1"] > el["bbox"]["y0"]
        assert 0 <= el["confidence"] <= 1
        assert el["text"].strip()
    assert any("TENDER NOTICE" in el["text"] for el in elements)

    # Raw file must be in MinIO.
    from app.core.config import get_settings
    from app.storage import ObjectStorage

    storage = ObjectStorage(get_settings())
    assert storage.exists(body["object_key"])


@pytest.mark.integration
async def test_upload_scanned_pdf_routes_to_ocr_and_succeeds(owner_conn):
    org_id = await create_org(owner_conn)
    ocr = FakeOcr(confidence=0.92)
    app = make_app(ladder=_ladder_with(ocr))

    async with client_for(app, org_id=org_id) as client:
        response = await upload(client, SCANNED)
        assert response.status_code == 201, response.text
        tender_id = response.json()["tender_id"]
        detail = (await client.get(f"/tenders/{tender_id}")).json()

    assert ocr.calls == [1, 2]
    assert detail["parse"]["status"] == "succeeded"
    assert detail["parse"]["pages_ocr"] == 2
    assert all(p["route"] == "ocr" for p in detail["pages"])


@pytest.mark.integration
async def test_upload_low_confidence_scan_flags_needs_human(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(ladder=_ladder_with(FakeOcr(confidence=0.3)))

    async with client_for(app, org_id=org_id) as client:
        response = await upload(client, SCANNED)
        tender_id = response.json()["tender_id"]
        detail = (await client.get(f"/tenders/{tender_id}")).json()

    assert detail["parse"]["status"] == "needs_human"
    assert detail["parse"]["pages_flagged"] == 2
    assert all(p["status"] == "flagged" for p in detail["pages"])


@pytest.mark.integration
async def test_duplicate_upload_same_org_conflicts(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app()

    async with client_for(app, org_id=org_id) as client:
        first = await upload(client, DIGITAL)
        assert first.status_code == 201
        second = await upload(client, DIGITAL)
    assert second.status_code == 409


@pytest.mark.integration
async def test_parse_run_logged_with_cost_and_trace(owner_conn):
    org_id = await create_org(owner_conn)
    logger = CaptureLogger()
    app = make_app(logger=logger)

    async with client_for(app, org_id=org_id) as client:
        response = await upload(client, DIGITAL)
        tender_id = response.json()["tender_id"]

    assert len(logger.entries) == 1
    entry = logger.entries[0]
    assert entry.trace_id == uuid.UUID(tender_id).hex
    assert entry.status == "succeeded"
    assert entry.pages_total == 2
    assert entry.cost_inr == 0.0  # local engines; rate is config
    assert entry.duration_s >= 0


# --- Grounding enforced in the data layer (§9 rule 1) ----------------------


@pytest.mark.integration
async def test_element_grounding_enforced_in_db(owner_conn):
    org_id = await create_org(owner_conn)

    async def seed_doc():
        doc_id, run_id = uuid.uuid4(), uuid.uuid4()
        tender_id = uuid.uuid4()
        await owner_conn.execute(
            text(
                "INSERT INTO tenders (id, org_id, title, source) "
                "VALUES (:t, :o, 'x', 'manual')"
            ),
            {"t": tender_id, "o": org_id},
        )
        await owner_conn.execute(
            text(
                "INSERT INTO documents (id, org_id, tender_id, filename, sha256,"
                " size_bytes, bucket, object_key) VALUES (:d, :o, :t, 'x.pdf',"
                " :sha, 10, 'b', :key)"
            ),
            {"d": doc_id, "o": org_id, "t": tender_id,
             "sha": uuid.uuid4().hex + uuid.uuid4().hex, "key": f"k/{doc_id}"},
        )
        await owner_conn.execute(
            text(
                "INSERT INTO pages (org_id, document_id, page_no, width, height,"
                " route, status, confidence) VALUES (:o, :d, 1, 612, 792,"
                " 'text', 'parsed', 0.9)"
            ),
            {"o": org_id, "d": doc_id},
        )
        await owner_conn.commit()
        return doc_id

    doc_id = await seed_doc()

    async def try_insert(**overrides):
        params = {
            "o": org_id, "d": doc_id, "p": 1, "k": "text_line", "t": "grounded",
            "x0": 1.0, "y0": 1.0, "x1": 5.0, "y1": 5.0, "c": 0.9, "s": 0,
        }
        params.update(overrides)
        await owner_conn.execute(
            text(
                "INSERT INTO elements (org_id, document_id, page_no, kind, text,"
                " x0, y0, x1, y1, confidence, seq) VALUES (:o, :d, :p, :k, :t,"
                " :x0, :y0, :x1, :y1, :c, :s)"
            ),
            params,
        )

    # Grounded insert works.
    await try_insert()
    await owner_conn.commit()

    # Each missing grounding field is unrepresentable.
    for bad in (
        {"t": "   "},               # blank text
        {"x1": 0.5},                # inverted bbox
        {"c": 1.5},                 # confidence out of range
        {"c": None},                # no confidence
        {"x0": None},               # no bbox
        {"p": 99},                  # page that does not exist
    ):
        with pytest.raises((IntegrityError, DBAPIError)):
            await try_insert(**bad)
        await owner_conn.rollback()


@pytest.mark.integration
async def test_parse_artifacts_isolated_by_rls(owner_conn, app_engine):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)

    app = make_app()
    async with client_for(app, org_id=org_a) as client:
        response = await upload(client, DIGITAL)
        assert response.status_code == 201

    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_b)},
        )
        for table in ("documents", "parse_runs", "pages", "elements"):
            rows = (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar()
            assert rows == 0, f"org B must not see org A rows in {table}"


def _ladder_with(ocr):
    from bidproof_parser import ParserLadder
    from bidproof_parser.engines import PdfiumTextExtractor

    return ParserLadder(PdfiumTextExtractor(), ocr)
