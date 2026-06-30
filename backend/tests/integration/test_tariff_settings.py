"""Tests for GET/PUT /tariff."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_tariff_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/tariff")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_viewer_can_read_tariff(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/tariff")
    assert response.status_code == 200
    body = response.json()
    assert "import_rate" in body
    assert "export_rate" in body
    assert "currency" in body


@pytest.mark.asyncio
async def test_admin_can_update_tariff(client: AsyncClient) -> None:
    data = await login(client, "admin", "admin-pass")
    response = await client.put(
        "/tariff",
        json={"import_rate": 0.28, "export_rate": 0.12, "currency": "GBP"},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["import_rate"] == 0.28
    assert body["export_rate"] == 0.12
    assert body["currency"] == "GBP"


@pytest.mark.asyncio
async def test_viewer_cannot_update_tariff(client: AsyncClient) -> None:
    data = await login(client, "viewer", "viewer-pass")
    response = await client.put(
        "/tariff",
        json={"import_rate": 0.99, "export_rate": 0.99, "currency": "GBP"},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 403
