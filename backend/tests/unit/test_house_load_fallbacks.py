"""House load resolution helpers — day series and recent-typical fallbacks."""

from datetime import datetime, timezone

import pytest

from app.adapters.sunsynk_connect import SunsynkConnectAdapter
from app.schemas.domain import HouseLoadSource, InverterMode, InverterStatus, LiveMetrics


def test_latest_series_value_returns_most_recent_non_idle() -> None:
    infos = [
        {
            "label": "Load",
            "records": [
                {"time": "09:00", "value": "0"},
                {"time": "09:05", "value": "420"},
                {"time": "09:10", "value": "380"},
            ],
        }
    ]
    watts, sample_at = SunsynkConnectAdapter._latest_series_value(
        infos, "Load", local_date="2026-06-30"
    )
    assert watts == pytest.approx(380)
    assert sample_at is not None
    assert sample_at.tzinfo is not None


def test_latest_series_value_empty() -> None:
    watts, sample_at = SunsynkConnectAdapter._latest_series_value(
        [], "Load", local_date="2026-06-30"
    )
    assert watts == 0.0
    assert sample_at is None


def test_apply_house_load_fallbacks_day_series() -> None:
    adapter = SunsynkConnectAdapter()
    metrics = LiveMetrics(
        pv_power_w=95,
        battery_soc_pct=95,
        battery_power_w=26,
        house_load_w=0,
        house_load_source=HouseLoadSource.MINIMAL,
        house_load_reported_w=0,
        grid_import_w=0,
        grid_export_w=136,
        inverter_mode=InverterMode.SELF_USE,
        inverter_status=InverterStatus.ONLINE,
        daily_pv_kwh=0,
        daily_import_kwh=0,
        daily_export_kwh=0,
        timestamp=datetime.now(timezone.utc),
    )
    sample_at = datetime(2026, 6, 30, 9, 10, tzinfo=timezone.utc)
    adapter._apply_house_load_fallbacks(
        metrics,
        latest_load_w=420,
        latest_load_at=sample_at,
        recent_typical=None,
    )
    assert metrics.house_load_w == pytest.approx(420)
    assert metrics.house_load_source == HouseLoadSource.DAY_SERIES
    assert metrics.house_load_at == sample_at


def test_apply_house_load_fallbacks_recent_typical() -> None:
    adapter = SunsynkConnectAdapter()
    metrics = LiveMetrics(
        pv_power_w=95,
        battery_soc_pct=95,
        battery_power_w=26,
        house_load_w=0,
        house_load_source=HouseLoadSource.MINIMAL,
        house_load_reported_w=0,
        grid_import_w=0,
        grid_export_w=136,
        inverter_mode=InverterMode.SELF_USE,
        inverter_status=InverterStatus.ONLINE,
        daily_pv_kwh=0,
        daily_import_kwh=0,
        daily_export_kwh=0,
        timestamp=datetime.now(timezone.utc),
    )
    recent_at = datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc)
    adapter._apply_house_load_fallbacks(
        metrics,
        latest_load_w=0,
        latest_load_at=None,
        recent_typical=(380, recent_at),
    )
    assert metrics.house_load_w == pytest.approx(380)
    assert metrics.house_load_source == HouseLoadSource.RECENT_TYPICAL
    assert metrics.house_load_at == recent_at


def test_resolve_house_load_source_labels() -> None:
    watts, source = SunsynkConnectAdapter._resolve_house_load(
        1800, pv=4200, grid_import=0, grid_export=2400, battery_power_w=600
    )
    assert watts == pytest.approx(1800)
    assert source == HouseLoadSource.REPORTED

    watts, source = SunsynkConnectAdapter._resolve_house_load(
        0, pv=9, grid_import=11, grid_export=0, battery_power_w=0
    )
    assert watts == pytest.approx(20)
    assert source == HouseLoadSource.DERIVED
