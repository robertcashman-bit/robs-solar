"""Integration tests: battery-plan diagnostics endpoint and config persistence (J)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_viewer_cannot_access_battery_plan(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/battery-plan")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_battery_plan_has_decision_picture(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    response = await client.get("/metrics/battery-plan")
    assert response.status_code == 200
    data = response.json()
    for key in (
        "tariff_timezone",
        "tariff_period",
        "battery_soc_pct",
        "battery_flow",
        "grid_flow",
        "daytime_floor_pct",
        "overnight_target_pct",
        "auto_align_enabled",
        "writes_enabled",
        "summary",
    ):
        assert key in data
    assert data["tariff_period"] in ("cheap", "peak")
    assert data["daytime_floor_pct"] < 95  # never a 95% reserve by default


@pytest.mark.asyncio
async def test_daytime_floor_persists_across_reads_and_restart(client: AsyncClient) -> None:
    session = await login(client, "admin", "admin-pass")
    csrf = session["csrf_token"]

    resp = await client.post(
        "/controls/auto-schedule",
        json={"enabled": True, "soc_floor_pct": 20},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    assert resp.json()["soc_floor_pct"] == 20

    # Re-read (and simulate a restart by clearing the in-memory singleton state).
    from app.services.auto_schedule_service import auto_schedule_service

    auto_schedule_service._last_run_at = None
    auto_schedule_service._computed_bands = []

    again = await client.get("/controls/auto-schedule")
    assert again.status_code == 200
    assert again.json()["soc_floor_pct"] == 20
    assert again.json()["enabled"] is True


@pytest.mark.asyncio
async def test_floor_at_95_is_rejected(client: AsyncClient) -> None:
    session = await login(client, "admin", "admin-pass")
    csrf = session["csrf_token"]
    resp = await client.post(
        "/controls/auto-schedule",
        json={"enabled": True, "soc_floor_pct": 95},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 422
