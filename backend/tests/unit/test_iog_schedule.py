"""Unit tests for IOG band computation."""

from datetime import datetime, timezone

from app.schemas.domain import DispatchWindow
from app.services.iog_schedule import (
    bands_equivalent,
    compute_iog_bands,
    merge_intervals,
    time_to_minutes,
)


def test_offpeak_only_produces_charge_and_discharge_bands() -> None:
    bands = compute_iog_bands(
        offpeak_start="23:30",
        offpeak_end="05:30",
        planned=[],
        soc_floor_pct=20,
    )
    assert len(bands) <= 6
    assert bands[0].start == "00:00"
    assert bands[0].target_soc_pct == 100
    assert bands[0].grid_charge_enabled is True
    discharge = next(b for b in bands if b.target_soc_pct == 20)
    assert discharge.grid_charge_enabled is False


def test_planned_dispatch_adds_charge_window() -> None:
    planned = [
        DispatchWindow(
            start=datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
            end=datetime(2026, 6, 30, 13, 0, tzinfo=timezone.utc),
            source="smart",
            delta_kwh=5.0,
        )
    ]
    bands = compute_iog_bands(
        offpeak_start="23:30",
        offpeak_end="05:30",
        planned=planned,
        soc_floor_pct=20,
        now=datetime(2026, 6, 30, 8, 0, tzinfo=timezone.utc),
    )
    assert len(bands) <= 6
    charge_starts = {b.start for b in bands if b.grid_charge_enabled}
    assert "00:00" in charge_starts


def test_bands_equivalent_ignores_power_w() -> None:
    from app.schemas.domain import TouBandWrite

    left = [
        TouBandWrite(
            slot=1, start="00:00", target_soc_pct=100, grid_charge_enabled=True, power_w=8000
        ),
        TouBandWrite(
            slot=2, start="05:30", target_soc_pct=20, grid_charge_enabled=False, power_w=9000
        ),
    ]
    right = [
        TouBandWrite(
            slot=1, start="00:00", target_soc_pct=100, grid_charge_enabled=True, power_w=3000
        ),
        TouBandWrite(
            slot=2, start="05:30", target_soc_pct=20, grid_charge_enabled=False, power_w=3000
        ),
    ]
    assert bands_equivalent(left, right)


def test_merge_intervals_wraps_midnight() -> None:
    merged = merge_intervals([(time_to_minutes("23:30"), time_to_minutes("05:30"))])
    assert merged == [(0, 330), (1410, 1440)]
