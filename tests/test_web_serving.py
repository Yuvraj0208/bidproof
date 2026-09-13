"""Serving the built web UI from the API process (single-container deploy).

When WEB_DIST points at a Vite build, the API serves it from "/" so one
container is the whole product: no second host, no CORS, one URL. The API
routes must still win over the catch-all, client-side routes must fall back
to index.html, and the fallback must never read outside the dist folder.
"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def dist(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>BidProof</title>")
    (tmp_path / "assets" / "app.js").write_text("console.log('ok')")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    monkeypatch.setenv("WEB_DIST", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def make_client() -> AsyncClient:
    from app.main import create_app

    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")


async def test_root_serves_index(dist):
    async with make_client() as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "BidProof" in response.text


async def test_client_route_falls_back_to_index(dist):
    async with make_client() as client:
        response = await client.get("/workspace/abc")
    assert response.status_code == 200
    assert "BidProof" in response.text


async def test_static_files_are_served(dist):
    async with make_client() as client:
        js = await client.get("/assets/app.js")
        icon = await client.get("/favicon.svg")
    assert js.status_code == 200 and "console.log" in js.text
    assert icon.status_code == 200 and "<svg" in icon.text


async def test_api_routes_still_win(dist):
    async with make_client() as client:
        health = await client.get("/health")
        # A real API path answers as the API, never as the UI — even when it
        # would refuse the request.
        proposal = await client.get("/tenders/abc/proposal")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert proposal.status_code == 400
    assert "X-Org-Id" in proposal.json()["detail"]


async def test_traversal_never_leaves_dist(dist):
    secret = dist.parent / "secret.txt"
    secret.write_text("nope")
    async with make_client() as client:
        response = await client.get("/../secret.txt")
        encoded = await client.get("/%2e%2e/secret.txt")
    for r in (response, encoded):
        assert "nope" not in r.text


async def test_without_web_dist_root_is_not_html(monkeypatch):
    monkeypatch.delenv("WEB_DIST", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    async with make_client() as client:
        response = await client.get("/workspace/abc")
    get_settings.cache_clear()
    assert response.status_code == 404
