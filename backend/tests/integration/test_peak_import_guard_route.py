"""Integration tests for peak import guard API."""


import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_viewer_cannot_access_peak_import_guard(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/peak-import-guard")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_read_peak_import_guard_status(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    response = await client.get("/metrics/peak-import-guard")
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert "armed" in data
    assert "consecutive_samples" in data


@pytest.mark.asyncio
async def test_admin_can_toggle_peak_import_guard(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await login(client, "admin", "admin-pass")
    csrf = session["csrf_token"]

    response = await client.post(
        "/controls/peak-import-guard",
        json={"enabled": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is True

    response = await client.post(
        "/controls/peak-import-guard",
        json={"enabled": False},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False


@pytest.mark.asyncio
async def test_peak_import_guard_toggle_requires_csrf(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    response = await client.post(
        "/controls/peak-import-guard",
        json={"enabled": True},
    )
    assert response.status_code == 403
