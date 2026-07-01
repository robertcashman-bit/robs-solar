"""Unit tests for live metrics integrity guard."""

from __future__ import annotations

import pytest

from app.schemas.domain import ConnectivityStatus, InverterSettingsResponse, LiveMetrics
from app.services.live_metrics_guard import LiveMetricsGuardError, assert_live_metrics_integrity


def _metrics() -> LiveMetrics:
    return LiveMetrics(
        pv_power_w=1000,
        battery_soc_pct=50.0,
        battery_power_w=0,
        house_load_w=800,
        grid_import_w=0,
        grid_export_w=200,
        inverter_mode="self_use",
        inverter_status="online",
        daily_pv_kwh=5.0,
        daily_import_kwh=1.0,
        daily_export_kwh=2.0,
        timestamp="2026-07-01T12:00:00Z",
    )


def test_guard_allows_simulator_mode(monkeypatch) -> None:
    monkeypatch.setattr("app.services.live_metrics_guard.is_live_mode", lambda: False)
    assert_live_metrics_integrity(_metrics())


def test_guard_rejects_simulator_connectivity(monkeypatch) -> None:
    monkeypatch.setattr("app.services.live_metrics_guard.is_live_mode", lambda: True)
    connectivity = ConnectivityStatus(
        backend_healthy=True,
        adapter_mode="simulator",
        adapter_connected=True,
    )
    with pytest.raises(LiveMetricsGuardError, match="simulator mode"):
        assert_live_metrics_integrity(_metrics(), connectivity=connectivity)


def test_guard_rejects_simulator_serial(monkeypatch) -> None:
    monkeypatch.setattr("app.services.live_metrics_guard.is_live_mode", lambda: True)
    settings_payload = InverterSettingsResponse(
        plant_id="537603",
        plant_name="Real Plant",
        inverter_sn="SIM-0001",
        inverter_mode="self_use",
        export_limit_w=5000,
        tou_bands=[],
    )
    with pytest.raises(LiveMetricsGuardError, match="SIM-0001"):
        assert_live_metrics_integrity(_metrics(), settings_payload=settings_payload)
