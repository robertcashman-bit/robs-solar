"""Unit tests for shared effective load resolution."""

from datetime import datetime, timezone

import pytest

from app.schemas.domain import HouseLoadSource, InverterMode, InverterStatus, LiveMetrics
from app.services.effective_load import (
    derived_house_load,
    finalize_live_metrics,
    resolve_house_load,
)


def test_resolve_house_load_prefers_derived_when_ct_underreports() -> None:
    watts, source = resolve_house_load(
        250,
        pv=0,
        grid_import=7200,
        grid_export=0,
        battery_power_w=0,
    )
    assert watts == pytest.approx(7200)
    assert source == HouseLoadSource.DERIVED


def test_resolve_house_load_trusts_reported_when_close_to_derived() -> None:
    watts, source = resolve_house_load(
        970,
        pv=30,
        grid_import=20,
        grid_export=0,
        battery_power_w=0,
    )
    assert watts == pytest.approx(970)
    assert source == HouseLoadSource.REPORTED


def test_finalize_live_metrics_derives_load_when_ct_reads_zero() -> None:
    metrics = LiveMetrics(
        pv_power_w=12,
        battery_soc_pct=95,
        battery_power_w=0,
        house_load_w=0,
        house_load_source=HouseLoadSource.MINIMAL,
        grid_import_w=13,
        grid_export_w=0,
        inverter_mode=InverterMode.SELF_USE,
        inverter_status=InverterStatus.ONLINE,
        daily_pv_kwh=0.6,
        daily_import_kwh=30,
        daily_export_kwh=0,
        timestamp=datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc),
    )
    finalized = finalize_live_metrics(metrics)
    assert finalized.house_load_w == pytest.approx(25.0)
    assert finalized.house_load_source == HouseLoadSource.DERIVED


def test_finalize_live_metrics_leaves_plausible_reported_load() -> None:
    metrics = LiveMetrics(
        pv_power_w=1700,
        battery_soc_pct=68,
        battery_power_w=600,
        house_load_w=1800,
        house_load_source=HouseLoadSource.REPORTED,
        grid_import_w=0,
        grid_export_w=500,
        inverter_mode=InverterMode.SELF_USE,
        inverter_status=InverterStatus.ONLINE,
        daily_pv_kwh=12,
        daily_import_kwh=3,
        daily_export_kwh=5,
        timestamp=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
    )
    finalized = finalize_live_metrics(metrics)
    assert finalized.house_load_w == pytest.approx(1800)
    assert finalized.house_load_source == HouseLoadSource.REPORTED


def test_finalize_live_metrics_matches_sunsynk_low_load_snapshot() -> None:
    """Mirrors live Sunsynk /flow: 9 W PV, 12 W grid import, 0 W CT, 1 W battery."""
    metrics = LiveMetrics(
        pv_power_w=9,
        battery_soc_pct=95,
        battery_power_w=1,
        house_load_w=0,
        house_load_source=HouseLoadSource.MINIMAL,
        house_load_reported_w=0,
        grid_import_w=12,
        grid_export_w=0,
        inverter_mode=InverterMode.SELF_USE,
        inverter_status=InverterStatus.ONLINE,
        daily_pv_kwh=0,
        daily_import_kwh=0,
        daily_export_kwh=0,
        timestamp=datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc),
    )
    finalized = finalize_live_metrics(metrics)
    assert finalized.house_load_w == pytest.approx(22.0)
    assert finalized.house_load_source == HouseLoadSource.DERIVED


def test_resolve_house_load_never_goes_negative_when_exporting_heavily() -> None:
    """Export exceeds PV+battery (e.g. metering glitch): balance goes negative,
    but the resolved load must clamp to 0, never a negative watt figure."""
    watts, source = resolve_house_load(
        0,
        pv=1000,
        grid_import=0,
        grid_export=2000,
        battery_power_w=0,
    )
    assert watts == pytest.approx(0.0)
    assert watts >= 0
    assert source == HouseLoadSource.MINIMAL


def test_derived_house_load_can_be_negative_before_clamping() -> None:
    """The raw balance formula itself is unclamped -- resolve_house_load clamps it."""
    balance = derived_house_load(pv=5000, grid_import=0, grid_export=4800, battery_power_w=-150)
    assert balance == pytest.approx(50.0)
    negative_balance = derived_house_load(
        pv=1000, grid_import=0, grid_export=2000, battery_power_w=0
    )
    assert negative_balance == pytest.approx(-1000.0)


def test_finalize_live_metrics_never_reports_negative_load() -> None:
    """A pathological negative derived balance must not surface as a negative load."""
    metrics = LiveMetrics(
        pv_power_w=100,
        battery_soc_pct=90,
        battery_power_w=0,
        house_load_w=0,
        house_load_source=HouseLoadSource.MINIMAL,
        grid_import_w=0,
        grid_export_w=900,  # export exceeds PV -- shouldn't happen, but must not go negative
        inverter_mode=InverterMode.SELF_USE,
        inverter_status=InverterStatus.ONLINE,
        daily_pv_kwh=1,
        daily_import_kwh=0,
        daily_export_kwh=1,
        timestamp=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
    )
    finalized = finalize_live_metrics(metrics)
    assert finalized.house_load_w >= 0
    assert finalized.house_load_w == pytest.approx(0.0)


def test_resolve_house_load_watts_are_not_reinterpreted_as_kilowatts() -> None:
    """Sunsynk /flow values are always watts; a small kW-scale number (e.g. 2.4)
    must not be mistaken for a large load -- it stays a small, plausible watt value."""
    watts, source = resolve_house_load(
        2.4,
        pv=0,
        grid_import=2.4,
        grid_export=0,
        battery_power_w=0,
    )
    assert watts == pytest.approx(2.4)
    assert source == HouseLoadSource.MINIMAL  # below the 5W noise floor either way


def test_finalize_live_metrics_preserves_high_load_kettle_scenario() -> None:
    """Heavy appliance: reported CT should stay trusted (kettle / oven scale)."""
    metrics = LiveMetrics(
        pv_power_w=0,
        battery_soc_pct=55,
        battery_power_w=100,
        house_load_w=2700,
        house_load_source=HouseLoadSource.REPORTED,
        house_load_reported_w=2700,
        grid_import_w=2800,
        grid_export_w=0,
        inverter_mode=InverterMode.SELF_USE,
        inverter_status=InverterStatus.ONLINE,
        daily_pv_kwh=0.6,
        daily_import_kwh=31,
        daily_export_kwh=0,
        timestamp=datetime(2026, 7, 1, 18, 0, tzinfo=timezone.utc),
    )
    finalized = finalize_live_metrics(metrics)
    assert finalized.house_load_w == pytest.approx(2700)
    assert finalized.house_load_source == HouseLoadSource.REPORTED
