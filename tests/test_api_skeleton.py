"""API skeleton: health endpoint and the org-scoped tenders stub."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text


def make_client() -> AsyncClient:
    from app.main import create_app

    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")


async def test_health_returns_200_and_db_status():
    async with make_client() as client:
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] in {"ok", "unreachable"}


async def test_tenders_requires_org_context():
    async with make_client() as client:
        response = await client.get("/tenders")
    assert response.status_code == 400
    assert "X-Org-Id" in response.json()["detail"]


async def test_tenders_rejects_malformed_org_id():
    async with make_client() as client:
        response = await client.get("/tenders", headers={"X-Org-Id": "not-a-uuid"})
    assert response.status_code == 400


@pytest.mark.integration
async def test_tenders_returns_empty_list_for_valid_org(owner_conn):
    org_id = uuid.uuid4()
    await owner_conn.execute(
        text("INSERT INTO organizations (id, name, slug) VALUES (:id, 'Org A', 'org-a')"),
        {"id": org_id},
    )
    await owner_conn.commit()

    async with make_client() as client:
        response = await client.get("/tenders", headers={"X-Org-Id": str(org_id)})
    assert response.status_code == 200
    assert response.json() == []
