"""Read-only settings watcher tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.adapters.simulator import SimulatorAdapter
from app.db.models import AppSettingRow, SettingsWatchChangeRow
from app.db.session import SessionLocal
from app.services.settings_watch_service import (
    diff_snapshots,
    fingerprint_snapshot,
    normalize_settings_snapshot,
    settings_watch_service,
)
from tests.conftest import login


@pytest.fixture(autouse=True)
async def _reset_settings_watch() -> None:
    async with SessionLocal() as db:
        await db.execute(delete(SettingsWatchChangeRow))
        await db.execute(
            delete(AppSettingRow).where(
                AppSettingRow.key.in_(
                    [
                        "settings_watch_last_fingerprint",
                        "settings_watch_last_snapshot",
                    ]
                )
            )
        )
        await db.commit()
    yield


@pytest.mark.asyncio
async def test_settings_watch_baseline_and_change(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")

    status = await client.get("/controls/settings-watch/status")
    assert status.status_code == 200
    assert status.json()["read_only"] is True

    first = await client.post("/controls/settings-watch/poll")
    assert first.status_code == 200
    assert first.json()["changed"] is True

    second = await client.post("/controls/settings-watch/poll")
    assert second.status_code == 200
    assert second.json()["changed"] is False

    adapter = SimulatorAdapter()
    settings_payload = await adapter.get_inverter_settings()
    mutated = settings_payload.model_copy(update={"solar_sell": False, "sys_work_mode": "9"})

    async with SessionLocal() as db:
        event = await settings_watch_service.observe_payload(db, mutated, source="test")
        assert event is not None

    changes = await client.get("/controls/settings-watch/changes?limit=10")
    assert changes.status_code == 200
    body = changes.json()
    assert body["count"] >= 2
    latest = body["changes"][0]
    fields = {item["field"] for item in latest["changes"]}
    assert "solar_sell" in fields or "sys_work_mode" in fields


def test_fingerprint_stable_for_same_snapshot() -> None:
    # sync helper — use normalized dict only
    snap = {
        "sys_work_mode": "1",
        "sys_work_mode_label": "Limited",
        "energy_mode": "1",
        "solar_sell": True,
        "export_limit_mode": "1",
        "discharge_current_a": 200,
        "bands": [
            {
                "slot": 1,
                "start": "00:00",
                "end": "05:30",
                "target_soc_pct": 100,
                "grid_charge_enabled": True,
                "power_w": 8000,
            }
        ],
        "active_band_slot": 1,
        "plant_id": "x",
        "plant_name": "y",
    }
    assert fingerprint_snapshot(snap) == fingerprint_snapshot(dict(snap))
    other = dict(snap)
    other["solar_sell"] = False
    assert fingerprint_snapshot(snap) != fingerprint_snapshot(other)
    diffs = diff_snapshots(snap, other)
    assert any(d["field"] == "solar_sell" for d in diffs)


@pytest.mark.asyncio
async def test_normalize_from_simulator_settings() -> None:
    adapter = SimulatorAdapter()
    payload = await adapter.get_inverter_settings()
    snap = normalize_settings_snapshot(payload)
    assert "bands" in snap
    assert snap["solar_sell"] is True
    assert fingerprint_snapshot(snap)
