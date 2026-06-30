"""Unit tests for cheap-window import explainer logic."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.schemas.domain import DispatchWindow, TouBand
from app.services.charge_window_service import evaluate_charge_window

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
    assert status.active is True
    assert "on purpose" in status.message.lower()
    assert "12:30" in status.message


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
    assert status.message == ""


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
    assert "no cheap" in status.message.lower()


def test_off_peak_window_detected() -> None:
    # 02:00 London = 01:00 UTC in winter; use a winter date for clarity
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
