"""Unit tests for deriving daily energy totals from the Sunsynk day series."""

import pytest

from app.adapters.sunsynk_connect import SunsynkConnectAdapter


def _records(values: list[float]) -> list[dict]:
    return [{"time": f"{i:02d}:00", "value": str(v)} for i, v in enumerate(values)]


def test_integrate_day_series_import_and_pv() -> None:
    # _records uses hourly timestamps (00:00, 01:00, ...) -> 1-hour step.
    # Grid positive = import, negative = export.
    infos = [
        {"label": "PV", "records": _records([0, 0, 1000, 2000, 1000, 0] + [0] * 6)},
        {"label": "Grid", "records": _records([3000, 3000, -500, -1000, 0, 0] + [0] * 6)},
        {"label": "Load", "records": _records([500] * 12)},
    ]
    totals = SunsynkConnectAdapter._integrate_day_series(infos)
    # step = 1h. PV: (1000+2000+1000)*1/1000 = 4.0 kWh
    assert totals["pv"] == 4.0
    # Grid import (positive): (3000+3000)*1/1000 = 6.0 kWh
    assert totals["import"] == 6.0
    # Grid export (negative magnitude): (500+1000)*1/1000 = 1.5 kWh
    assert totals["export"] == 1.5


def test_integrate_day_series_five_minute_cadence() -> None:
    # Realistic partial-day feed: 5-minute spacing. A steady 6 kW import for one
    # hour (12 samples) should be ~6 kWh regardless of how many samples exist.
    records = [
        {"time": f"{(i * 5) // 60:02d}:{(i * 5) % 60:02d}", "value": "6000"} for i in range(12)
    ]
    totals = SunsynkConnectAdapter._integrate_day_series([{"label": "Grid", "records": records}])
    # 12 samples * 5min * 6000W -> 6.0 kWh
    assert abs(totals["import"] - 6.0) < 0.01


def test_integrate_day_series_handles_missing_and_bad_values() -> None:
    infos = [
        {"label": "Grid", "records": [{"value": "abc"}, {"value": None}, {"value": "100"}]},
    ]
    totals = SunsynkConnectAdapter._integrate_day_series(infos)
    assert totals["pv"] == 0.0
    assert totals["export"] == 0.0
    # Only the 100W sample counts; step defaults from 3 records -> 8h.
    assert totals["import"] > 0.0


def test_integrate_day_series_empty() -> None:
    totals = SunsynkConnectAdapter._integrate_day_series([])
    assert totals == {"pv": 0.0, "import": 0.0, "export": 0.0}


def test_latest_series_value_skips_idle_tail() -> None:
    infos = [
        {
            "label": "Load",
            "records": [
                {"time": "10:00", "value": "500"},
                {"time": "10:05", "value": "2"},
            ],
        }
    ]
    watts, _ = SunsynkConnectAdapter._latest_series_value(infos, "Load", local_date="2026-06-30")
    assert watts == pytest.approx(500)
