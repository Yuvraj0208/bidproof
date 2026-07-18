"""US-01 integration: discovery end-to-end through the SAME pipeline as
manual upload — tender ingested, duplicate collapsed, failing adapter
contained, run recorded, RLS scoping intact."""

import uuid

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from bidproof_adapters import DiscoveredTender, DomainAllowList, GuardedFetcher
from test_parser_ladder import DIGITAL
from test_upload_api import create_org

pytestmark = pytest.mark.integration

PDF_URL = "https://portal.test/docs/tender.pdf"


class StubPortal:
    name = "stubportal"
    allowed_domains = ("portal.test",)

    def __init__(self, tenders):
        self._tenders = tenders

    async def discover(self, fetcher):
        return list(self._tenders)


class ExplodingPortal:
    name = "exploding"
    allowed_domains = ("portal.test",)

    async def discover(self, fetcher):
        raise RuntimeError("markup changed")


def discovered(external_id="STUB/2026/001", pdf=True):
    return DiscoveredTender(
        portal="stubportal",
        external_id=external_id,
        title=f"Stub tender {external_id}",
        url=f"https://portal.test/t/{external_id}",
        pdf_url=PDF_URL if pdf else None,
    )


def make_app(adapters):
    from app.main import create_app
    from app.services.discovery import get_adapters, get_discovery_fetcher

    def transport_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == PDF_URL:
            return httpx.Response(200, content=DIGITAL)
        return httpx.Response(404)

    fetcher = GuardedFetcher(
        DomainAllowList(["portal.test"]),
        client=httpx.AsyncClient(transport=httpx.MockTransport(transport_handler)),
    )
    app = create_app()
    app.dependency_overrides[get_adapters] = lambda: adapters
    app.dependency_overrides[get_discovery_fetcher] = lambda: fetcher
    return app


def client_for(app, org_id):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Org-Id": str(org_id)},
    )


async def test_discovery_ingests_new_tender_end_to_end(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app([StubPortal([discovered()])])

    async with client_for(app, org_id) as client:
        response = await client.post("/discovery/run")
        assert response.status_code == 200, response.text
        report = response.json()
        run = next(r for r in report["runs"] if r["adapter"] == "stubportal")
        assert run["ok"] and run["discovered"] == 1 and run["ingested"] == 1

        tenders = (await client.get("/tenders")).json()
        assert len(tenders) == 1
        assert tenders[0]["source"] == "stubportal"
        tender_id = tenders[0]["id"]

        detail = (await client.get(f"/tenders/{tender_id}")).json()
        assert detail["parse"]["status"] == "succeeded"

        elements = (
            await client.get(f"/tenders/{tender_id}/elements", params={"page_no": 1})
        ).json()

    assert elements, "a scraped tender must flow through the SAME parse pipeline"
    assert all(e["el_id"] and e["bbox"]["x1"] > e["bbox"]["x0"] for e in elements)


async def test_duplicate_discovery_is_collapsed(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app([StubPortal([discovered()])])

    async with client_for(app, org_id) as client:
        first = (await client.post("/discovery/run")).json()
        second = (await client.post("/discovery/run")).json()
        tenders = (await client.get("/tenders")).json()

    run1 = next(r for r in first["runs"] if r["adapter"] == "stubportal")
    run2 = next(r for r in second["runs"] if r["adapter"] == "stubportal")
    assert run1["ingested"] == 1
    assert run2["ingested"] == 0
    assert run2["duplicates"] == 1
    assert len(tenders) == 1, "the same portal tender must appear exactly once"


async def test_failing_adapter_does_not_stop_ingestion(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app([ExplodingPortal(), StubPortal([discovered("STUB/2026/002")])])

    async with client_for(app, org_id) as client:
        report = (await client.post("/discovery/run")).json()
        tenders = (await client.get("/tenders")).json()

    exploding = next(r for r in report["runs"] if r["adapter"] == "exploding")
    stub = next(r for r in report["runs"] if r["adapter"] == "stubportal")
    assert not exploding["ok"] and "markup changed" in exploding["error"]
    assert stub["ok"] and stub["ingested"] == 1
    assert len(tenders) == 1


async def test_discovery_run_is_recorded(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app([StubPortal([discovered("STUB/2026/003")])])

    async with client_for(app, org_id) as client:
        await client.post("/discovery/run")
        runs = (await client.get("/discovery/runs")).json()

    assert len(runs) == 1
    assert runs[0]["finished_at"] is not None
    adapters_reported = [r["adapter"] for r in runs[0]["report"]["runs"]]
    assert "stubportal" in adapters_reported


async def test_discovered_tenders_respect_rls(owner_conn, app_engine):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    app = make_app([StubPortal([discovered("STUB/2026/004")])])

    async with client_for(app, org_a) as client:
        await client.post("/discovery/run")

    async with app_engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"),
            {"o": str(org_b)},
        )
        count = (await conn.execute(text("SELECT count(*) FROM tenders"))).scalar()
    assert count == 0, "org B must not see org A's discovered tenders"
