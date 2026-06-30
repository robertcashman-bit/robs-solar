import pytest
from httpx import AsyncClient

from app.config import settings
from tests.conftest import login


@pytest.mark.asyncio
async def test_admin_export_limit_write_success(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    response = await client.post(
        "/controls/export-limit",
        json={"limit_w": 3000},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["applied_value"]["export_limit_w"] == 3000


_TOU_BODY = {
    "bands": [
        {
            "slot": 1,
            "start": "00:00",
            "target_soc_pct": 100,
            "grid_charge_enabled": True,
            "power_w": 3000,
        },
        {
            "slot": 2,
            "start": "06:00",
            "target_soc_pct": 40,
            "grid_charge_enabled": False,
            "power_w": 8000,
        },
    ]
}


@pytest.mark.asyncio
async def test_admin_tou_write_success(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    response = await client.post(
        "/controls/tou",
        json=_TOU_BODY,
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["applied_value"]["bands"] == 2


@pytest.mark.asyncio
async def test_viewer_cannot_write_tou(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "viewer", "viewer-pass")
    response = await client.post(
        "/controls/tou",
        json=_TOU_BODY,
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tou_write_without_csrf_rejected(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "read_only", False)
    await login(client, "admin", "admin-pass")
    response = await client.post("/controls/tou", json=_TOU_BODY)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tou_write_blocked_in_read_only(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "read_only", True)
    data = await login(client, "admin", "admin-pass")
    response = await client.post(
        "/controls/tou",
        json=_TOU_BODY,
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_write_export_limit(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "viewer", "viewer-pass")
    response = await client.post(
        "/controls/export-limit",
        json={"limit_w": 3000},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_write_without_csrf_rejected(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "read_only", False)
    await login(client, "admin", "admin-pass")
    response = await client.post("/controls/export-limit", json={"limit_w": 3000})
    assert response.status_code == 403
