"""Golden Sunsynk flow scenarios — energy balance must close for every case."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.adapters.sunsynk_connect import SunsynkConnectAdapter

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "sunsynk_flow_scenarios.json"


def _scenarios() -> list[dict]:
    return json.loads(FIXTURES.read_text())


def _balance_error(
    *,
    pv: float,
    grid_import: float,
    grid_export: float,
    battery: float,
    house_load: float,
) -> float:
    supply = pv + grid_import - grid_export + battery
    return abs(house_load - supply)


@pytest.mark.parametrize("scenario", _scenarios(), ids=lambda s: s["id"])
def test_sunsynk_flow_scenario(scenario: dict) -> None:
    adapter = SunsynkConnectAdapter(client=httpx.AsyncClient())
    metrics = adapter._parse_flow(scenario["payload"])
    expected = scenario["expected"]

    for key, value in expected.items():
        actual = getattr(metrics, key)
        if key == "house_load_source":
            actual = actual.value if hasattr(actual, "value") else actual
        if isinstance(value, (int, float)):
            assert actual == pytest.approx(value, abs=2), key
        else:
            assert actual == value, key

    if scenario.get("skip_balance_check"):
        return

    assert _balance_error(
        pv=metrics.pv_power_w,
        grid_import=metrics.grid_import_w,
        grid_export=metrics.grid_export_w,
        battery=metrics.battery_power_w,
        house_load=metrics.house_load_w,
    ) < 2


def test_low_load_metrics_for_frontend() -> None:
    """Cross-layer: parsed metrics for the user's low-load bug snapshot."""
    scenario = next(s for s in _scenarios() if s["id"] == "low_load_grid_solar")
    adapter = SunsynkConnectAdapter(client=httpx.AsyncClient())
    metrics = adapter._parse_flow(scenario["payload"])
    assert metrics.house_load_w == pytest.approx(20, abs=2)
    assert metrics.grid_import_w == pytest.approx(11, abs=2)
