"""Unit tests for peak import guard automatic remediation."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest

from app.adapters.simulator import SimulatorAdapter
from app.db.session import SessionLocal
from app.schemas.domain import (
    AutoScheduleStatus,
    ControlWriteResult,
    InverterMode,
    InverterStatus,
    LiveMetrics,
    PeakImportGuardConfigRequest,
)
from app.services.peak_import_guard_service import (
    PeakImportGuardService,
    peak_import_guard_service,
    should_remediate,
)


def _peak_metrics(
    *,
    grid_import_w: float = 500.0,
    battery_soc_pct: float = 96.0,
    battery_power_w: Optional[float] = 50.0,
    mode: InverterMode = InverterMode.FEED_IN,
) -> LiveMetrics:
    return LiveMetrics(
        pv_power_w=31.0,
        battery_soc_pct=battery_soc_pct,
        battery_power_w=battery_power_w,
        house_load_w=972.0,
        grid_import_w=grid_import_w,
        grid_export_w=0.0,
        inverter_mode=mode,
        inverter_status=InverterStatus.ONLINE,
        daily_pv_kwh=1.0,
        daily_import_kwh=0.5,
        daily_export_kwh=0.0,
        timestamp=datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
    )


def test_should_remediate_peak_import_at_high_soc() -> None:
    assert should_remediate(
        cheap_now=False,
        grid_import_w=500.0,
        battery_soc_pct=96.0,
        battery_power_w=50.0,
        soc_floor_pct=20,
        import_threshold_w=100.0,
    )


def test_should_not_remediate_below_import_threshold() -> None:
    assert not should_remediate(
        cheap_now=False,
        grid_import_w=19.0,
        battery_soc_pct=96.0,
        battery_power_w=50.0,
        soc_floor_pct=20,
        import_threshold_w=100.0,
    )


def test_should_not_remediate_during_cheap_window() -> None:
    assert not should_remediate(
        cheap_now=True,
        grid_import_w=500.0,
        battery_soc_pct=96.0,
        battery_power_w=50.0,
        soc_floor_pct=20,
        import_threshold_w=100.0,
    )


def test_should_not_remediate_when_soc_at_floor() -> None:
    assert not should_remediate(
        cheap_now=False,
        grid_import_w=500.0,
        battery_soc_pct=24.0,
        battery_power_w=50.0,
        soc_floor_pct=20,
        import_threshold_w=100.0,
    )


def test_should_not_remediate_when_discharging_enough() -> None:
    assert not should_remediate(
        cheap_now=False,
        grid_import_w=500.0,
        battery_soc_pct=96.0,
        battery_power_w=150.0,
        soc_floor_pct=20,
        import_threshold_w=100.0,
    )


@pytest.mark.asyncio
async def test_requires_sustained_samples_before_remediation() -> None:
    guard = PeakImportGuardService()
    adapter = SimulatorAdapter()
    metrics = _peak_metrics()

    async with SessionLocal() as db:
        await guard.set_config(db, PeakImportGuardConfigRequest(enabled=True))

    with (
        patch(
            "app.services.peak_import_guard_service.safety_settings_service"
        ) as mock_safety,
        patch(
            "app.services.peak_import_guard_service.ev_load_detector"
        ) as mock_ev,
        patch.object(
            guard,
            "_remediate",
            new_callable=AsyncMock,
        ) as mock_remediate,
    ):
        mock_safety.effective_read_only.return_value = False
        mock_safety.effective_enable_live_writes.return_value = True
        mock_ev.car_charging_likely = False

        async with SessionLocal() as db:
            await guard.evaluate(db, metrics, adapter)
            assert mock_remediate.await_count == 0
            assert guard._consecutive_samples == 1

            await guard.evaluate(db, metrics, adapter)
            assert mock_remediate.await_count == 1


@pytest.mark.asyncio
async def test_respects_cooldown() -> None:
    guard = PeakImportGuardService()
    adapter = SimulatorAdapter()
    metrics = _peak_metrics()
    guard._last_action_at = datetime.now(timezone.utc)
    guard._consecutive_samples = 2

    with (
        patch(
            "app.services.peak_import_guard_service.safety_settings_service"
        ) as mock_safety,
        patch(
            "app.services.peak_import_guard_service.ev_load_detector"
        ) as mock_ev,
        patch.object(
            guard,
            "_remediate",
            new_callable=AsyncMock,
        ) as mock_remediate,
    ):
        mock_safety.effective_read_only.return_value = False
        mock_safety.effective_enable_live_writes.return_value = True
        mock_ev.car_charging_likely = False

        async with SessionLocal() as db:
            await guard.set_config(db, PeakImportGuardConfigRequest(enabled=True))
            await guard.evaluate(db, metrics, adapter)
            mock_remediate.assert_not_awaited()


@pytest.mark.asyncio
async def test_skips_when_ev_charging() -> None:
    guard = PeakImportGuardService()
    adapter = SimulatorAdapter()
    metrics = _peak_metrics()
    guard._consecutive_samples = 2
    guard._last_action_at = datetime.now(timezone.utc) - timedelta(minutes=60)

    with (
        patch(
            "app.services.peak_import_guard_service.safety_settings_service"
        ) as mock_safety,
        patch(
            "app.services.peak_import_guard_service.ev_load_detector"
        ) as mock_ev,
        patch.object(
            guard,
            "_remediate",
            new_callable=AsyncMock,
        ) as mock_remediate,
    ):
        mock_safety.effective_read_only.return_value = False
        mock_safety.effective_enable_live_writes.return_value = True
        mock_ev.car_charging_likely = True

        async with SessionLocal() as db:
            await guard.set_config(db, PeakImportGuardConfigRequest(enabled=True))
            await guard.evaluate(db, metrics, adapter)
            mock_remediate.assert_not_awaited()


@pytest.mark.asyncio
async def test_skips_when_writes_disabled() -> None:
    guard = PeakImportGuardService()
    adapter = SimulatorAdapter()
    metrics = _peak_metrics()
    guard._consecutive_samples = 2
    guard._last_action_at = datetime.now(timezone.utc) - timedelta(minutes=60)

    with (
        patch(
            "app.services.peak_import_guard_service.safety_settings_service"
        ) as mock_safety,
        patch(
            "app.services.peak_import_guard_service.ev_load_detector"
        ) as mock_ev,
        patch.object(
            guard,
            "_remediate",
            new_callable=AsyncMock,
        ) as mock_remediate,
    ):
        mock_safety.effective_read_only.return_value = True
        mock_safety.effective_enable_live_writes.return_value = False
        mock_ev.car_charging_likely = False

        async with SessionLocal() as db:
            await guard.set_config(db, PeakImportGuardConfigRequest(enabled=True))
            await guard.evaluate(db, metrics, adapter)
            mock_remediate.assert_not_awaited()


@pytest.mark.asyncio
async def test_remediation_sequence_enable_mode_align() -> None:
    guard = PeakImportGuardService()
    adapter = SimulatorAdapter()
    metrics = _peak_metrics(mode=InverterMode.FEED_IN)

    mock_set_config = AsyncMock()
    mock_set_mode = AsyncMock(
        return_value=ControlWriteResult(success=True, message="ok", audit_id=42)
    )
    mock_run_once = AsyncMock(
        return_value=AutoScheduleStatus(
            enabled=True,
            soc_floor_pct=20,
            last_run_message="Schedule updated",
            last_write_audit_id=99,
        )
    )

    with (
        patch.object(
            guard,
            "_resolve_charge_context",
            new_callable=AsyncMock,
            return_value=("23:30", "05:30", [], None),
        ),
        patch(
            "app.services.peak_import_guard_service.auto_schedule_service.set_config",
            mock_set_config,
        ),
        patch(
            "app.services.peak_import_guard_service.control_service.set_operating_mode",
            mock_set_mode,
        ),
        patch(
            "app.services.peak_import_guard_service.auto_schedule_service.run_once",
            mock_run_once,
        ),
    ):
        async with SessionLocal() as db:
            await guard._remediate(
                db,
                adapter,
                metrics,
                {"enabled": False, "soc_floor_pct": 20},
            )

    mock_set_config.assert_awaited_once()
    mock_set_mode.assert_awaited_once()
    mock_run_once.assert_awaited_once()
    assert "enabled auto-align" in guard._last_action_message
    assert "self-use" in guard._last_action_message
    assert guard._last_audit_ids == [42, 99]


@pytest.mark.asyncio
async def test_disabled_guard_resets_counters() -> None:
    guard = PeakImportGuardService()
    adapter = SimulatorAdapter()
    metrics = _peak_metrics()
    guard._consecutive_samples = 2

    async with SessionLocal() as db:
        await guard.set_config(db, PeakImportGuardConfigRequest(enabled=False))
        await guard.evaluate(db, metrics, adapter)
        assert guard._consecutive_samples == 0
        assert guard._armed is False


@pytest.mark.asyncio
async def test_singleton_module_export() -> None:
    assert peak_import_guard_service is not None
