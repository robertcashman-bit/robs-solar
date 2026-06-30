"""Unit tests for cheap-window import explainer logic."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.schemas.domain import DispatchWindow, TouBand
from app.services.charge_window_service import (
    evaluate_charge_window,
    next_cheap_window_start,
)

LONDON = ZoneInfo("Europe/London")


def _band(*, start: str, end: str, grid_charge: bool, cap: int = 100) -> TouBand:
    return TouBand(
        slot=1,
        start=start,
        end=end,
        target_soc_pct=cap,
        grid_charge_enabled=grid_charge,
        power_w=8000,
    )


def test_importing_on_smart_charge_window() -> None:
    # Midday smart-charge 12:01-12:30, now 12:15 London
    now = datetime(2026, 6, 30, 11, 15, tzinfo=timezone.utc)  # 12:15 BST
    planned = [
        DispatchWindow(
            start=datetime(2026, 6, 30, 11, 1, tzinfo=timezone.utc),
            end=datetime(2026, 6, 30, 11, 30, tzinfo=timezone.utc),
            source="smart-charge",
        )
    ]
    status = evaluate_charge_window(
        grid_import_w=389.0,
        battery_soc_pct=100.0,
        battery_power_w=-54.0,
        active_band=_band(start="12:01", end="12:30", grid_charge=True),
        offpeak_start="23:30",
        offpeak_end="05:30",
        planned=planned,
        now=now,
    )
    assert status.importing_on_cheap_window is True
    assert status.source == "smart-charge"
    assert status.state == "cheap_import"
    assert status.cheap_now is True
    assert status.active is True
    assert "cheap power" in status.message.lower()


def test_cheap_import_without_grid_charge_holding() -> None:
    now = datetime(2026, 6, 30, 11, 15, tzinfo=timezone.utc)
    planned = [
        DispatchWindow(
            start=datetime(2026, 6, 30, 11, 1, tzinfo=timezone.utc),
            end=datetime(2026, 6, 30, 11, 30, tzinfo=timezone.utc),
            source="smart-charge",
        )
    ]
    status = evaluate_charge_window(
        grid_import_w=500.0,
        battery_soc_pct=99.0,
        battery_power_w=-30.0,
        active_band=_band(start="14:00", end="23:30", grid_charge=False, cap=20),
        offpeak_start="23:30",
        offpeak_end="05:30",
        planned=planned,
        now=now,
    )
    assert status.importing_on_cheap_window is True
    assert status.state == "cheap_import"


def test_not_active_outside_cheap_window() -> None:
    now = datetime(2026, 6, 30, 10, 0, tzinfo=timezone.utc)  # 11:00 BST
    status = evaluate_charge_window(
        grid_import_w=0.0,
        battery_soc_pct=80.0,
        battery_power_w=500.0,
        active_band=_band(start="05:30", end="23:30", grid_charge=False, cap=20),
        offpeak_start="23:30",
        offpeak_end="05:30",
        planned=[],
        now=now,
    )
    assert status.importing_on_cheap_window is False
    assert status.state == "idle"
    assert status.cheap_now is False
    assert status.message == ""
    assert status.next_cheap_start is not None


def test_peak_import_at_full_battery_without_grid_charge() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)  # 13:00 BST peak
    status = evaluate_charge_window(
        grid_import_w=777.0,
        battery_soc_pct=99.0,
        battery_power_w=-34.0,
        active_band=_band(start="14:00", end="23:30", grid_charge=False, cap=20),
        offpeak_start="23:30",
        offpeak_end="05:30",
        planned=[],
        now=now,
    )
    assert status.state == "peak_import"
    assert status.cheap_now is False
    assert status.importing_on_cheap_window is False
    assert "peak" in status.message.lower()
    assert status.severity == "info"


def test_holding_and_importing_without_cheap_window_warns() -> None:
    now = datetime(2026, 6, 30, 10, 0, tzinfo=timezone.utc)
    status = evaluate_charge_window(
        grid_import_w=300.0,
        battery_soc_pct=95.0,
        battery_power_w=0.0,
        active_band=_band(start="10:00", end="14:00", grid_charge=True),
        offpeak_start="23:30",
        offpeak_end="05:30",
        planned=[],
        now=now,
    )
    assert status.importing_on_cheap_window is False
    assert status.source == "unexpected"
    assert status.state == "peak_import"
    assert status.severity == "caution"
    assert "no cheap" in status.message.lower()


def test_off_peak_window_detected() -> None:
    now = datetime(2026, 1, 15, 2, 0, tzinfo=LONDON)
    status = evaluate_charge_window(
        grid_import_w=2000.0,
        battery_soc_pct=50.0,
        battery_power_w=-100.0,
        active_band=_band(start="00:00", end="05:30", grid_charge=True),
        offpeak_start="23:30",
        offpeak_end="05:30",
        planned=[],
        now=now,
    )
    assert status.importing_on_cheap_window is True
    assert status.source == "off-peak"
    assert status.cheap_now is True
    assert status.next_cheap_start is None


def test_next_cheap_start_when_on_peak() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    next_start, source = next_cheap_window_start(
        now,
        "23:30",
        "05:30",
        [],
    )
    assert next_start is not None
    assert source == "off-peak"


def test_next_cheap_start_none_when_cheap_now() -> None:
    now = datetime(2026, 1, 15, 2, 0, tzinfo=LONDON)
    next_start, source = next_cheap_window_start(
        now,
        "23:30",
        "05:30",
        [],
    )
    assert next_start is None
    assert source == ""
