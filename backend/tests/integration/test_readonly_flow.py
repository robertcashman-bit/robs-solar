import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["adapter_mode"] == "simulator"
    assert body["read_only"] is True


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    data = await login(client, "admin", "admin-pass")
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "admin"
    assert "csrf_token" in data


@pytest.mark.asyncio
async def test_login_failure(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_viewer_can_read_metrics(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/live")
    assert response.status_code == 200
    body = response.json()
    assert "pv_power_w" in body
    assert "battery_soc_pct" in body


@pytest.mark.asyncio
async def test_viewer_cannot_read_audit(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/audit")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_read_audit(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    response = await client.get("/audit")
    assert response.status_code == 200
    body = response.json()
    assert "entries" in body


@pytest.mark.asyncio
async def test_read_only_blocks_export_limit_write(client: AsyncClient) -> None:
    data = await login(client, "admin", "admin-pass")
    response = await client.post(
        "/controls/export-limit",
        json={"limit_w": 2000},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 403
    assert "read-only" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unauthenticated_metrics_rejected(client: AsyncClient) -> None:
    response = await client.get("/metrics/live")
    assert response.status_code == 401
