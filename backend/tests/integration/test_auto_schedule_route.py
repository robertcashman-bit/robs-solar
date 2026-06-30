"""Integration tests for auto-schedule controls."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_viewer_cannot_access_auto_schedule(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/controls/auto-schedule")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_read_auto_schedule_status(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    response = await client.get("/controls/auto-schedule")
    assert response.status_code == 200
    body = response.json()
    assert "enabled" in body
    assert isinstance(body["soc_floor_pct"], int)
    assert 0 <= body["soc_floor_pct"] <= 100


@pytest.mark.asyncio
async def test_admin_can_toggle_auto_schedule(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    response = await client.post(
        "/controls/auto-schedule",
        json={"enabled": True, "soc_floor_pct": 25},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["soc_floor_pct"] == 25


@pytest.mark.asyncio
async def test_auto_schedule_toggle_requires_csrf(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    response = await client.post(
        "/controls/auto-schedule",
        json={"enabled": False},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_enabling_auto_schedule_triggers_immediate_realign(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.auto_schedule_service import auto_schedule_service

    run_calls: list[bool] = []
    original_run_once = auto_schedule_service.run_once

    async def track_run_once(db, adapter):
        run_calls.append(True)
        return await original_run_once(db, adapter)

    monkeypatch.setattr(auto_schedule_service, "run_once", track_run_once)

    data = await login(client, "admin", "admin-pass")
    response = await client.post(
        "/controls/auto-schedule",
        json={"enabled": True, "soc_floor_pct": 25},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["soc_floor_pct"] == 25
    assert body["last_run_message"]
    assert run_calls == [True]


@pytest.mark.asyncio
async def test_disabling_auto_schedule_skips_immediate_realign(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.auto_schedule_service import auto_schedule_service

    run_calls: list[bool] = []

    async def track_run_once(db, adapter):
        run_calls.append(True)
        raise AssertionError("run_once should not be called when disabling auto-align")

    monkeypatch.setattr(auto_schedule_service, "run_once", track_run_once)

    data = await login(client, "admin", "admin-pass")
    response = await client.post(
        "/controls/auto-schedule",
        json={"enabled": False},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert run_calls == []
