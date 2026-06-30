"""Resilience tests for auto-align: API failure (F) and restart (G)."""

from __future__ import annotations

from typing import Any

import pytest

from app.db.session import SessionLocal
from app.schemas.domain import (
    AdapterError,
    AutoScheduleConfigRequest,
    InverterSettingsResponse,
    TouBandWrite,
)
from app.services.auto_schedule_service import AutoScheduleService
from app.services.safety_settings_service import safety_settings_service


async def _fixed_bands(_db) -> list[TouBandWrite]:
    """Stub compute_bands so the failure test does not depend on the Octopus API."""
    return [
        TouBandWrite(slot=1, start="00:00", target_soc_pct=100,
                     grid_charge_enabled=True, power_w=8000),
        TouBandWrite(slot=2, start="05:30", target_soc_pct=20,
                     grid_charge_enabled=False, power_w=8000),
    ]


class _FailingAdapter:
    """Adapter whose TOU write always fails (simulates inverter rejection)."""

    def __init__(self) -> None:
        self.write_attempts = 0

    async def get_inverter_settings(self) -> InverterSettingsResponse:
        return InverterSettingsResponse(
            inverter_sn="SIM",
            write_allowed=True,
            bands=[],  # empty -> differs from desired -> a write is attempted
            active_band_slot=None,
            active_band=None,
        )

    async def set_tou_bands(self, request: Any) -> dict[str, Any]:
        self.write_attempts += 1
        raise AdapterError("inverter rejected settings write (rate limited)")


@pytest.mark.asyncio
async def test_api_failure_is_surfaced_not_faked(monkeypatch) -> None:
    monkeypatch.setattr(safety_settings_service, "effective_read_only", lambda: False)
    monkeypatch.setattr(
        safety_settings_service, "effective_enable_live_writes", lambda: True
    )
    service = AutoScheduleService()
    monkeypatch.setattr(service, "compute_bands", _fixed_bands)
    adapter = _FailingAdapter()

    async with SessionLocal() as db:
        await service.set_config(db, AutoScheduleConfigRequest(enabled=True, soc_floor_pct=20))
        status = await service.run_once(db, adapter)

    assert adapter.write_attempts == 1
    # The failure must be surfaced, and the app must NOT pretend it succeeded.
    assert "rejected" in status.last_run_message.lower()
    assert status.last_write_audit_id is None


@pytest.mark.asyncio
async def test_writes_disabled_does_not_silently_succeed(monkeypatch) -> None:
    monkeypatch.setattr(safety_settings_service, "effective_read_only", lambda: True)
    monkeypatch.setattr(
        safety_settings_service, "effective_enable_live_writes", lambda: False
    )
    service = AutoScheduleService()
    adapter = _FailingAdapter()

    async with SessionLocal() as db:
        await service.set_config(db, AutoScheduleConfigRequest(enabled=True, soc_floor_pct=20))
        status = await service.run_once(db, adapter)

    assert adapter.write_attempts == 0
    assert "writes disabled" in status.last_run_message.lower()
    assert status.last_write_audit_id is None


@pytest.mark.asyncio
async def test_config_survives_restart() -> None:
    # Instance 1 persists the config to the DB.
    first = AutoScheduleService()
    async with SessionLocal() as db:
        await first.set_config(db, AutoScheduleConfigRequest(enabled=True, soc_floor_pct=25))

    # Instance 2 simulates a process restart: fresh in-memory state, must read
    # the persisted settings back from the database.
    second = AutoScheduleService()
    assert second._last_run_at is None  # genuinely fresh
    async with SessionLocal() as db:
        status = await second.get_status(db)

    assert status.enabled is True
    assert status.soc_floor_pct == 25
