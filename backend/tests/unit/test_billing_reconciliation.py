"""Unit tests for billing reconciliation interval classification."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.billing_reconciliation_service import _interval_is_cheap
from app.services.iog_schedule import charge_intervals_from_windows


def test_interval_midpoint_in_offpeak_is_cheap() -> None:
    start = datetime(2026, 6, 30, 2, 0, tzinfo=ZoneInfo("Europe/London"))
    end = datetime(2026, 6, 30, 2, 30, tzinfo=ZoneInfo("Europe/London"))
    charge = charge_intervals_from_windows("23:30", "05:30", [])
    assert _interval_is_cheap(start, end, charge) is True


def test_interval_midpoint_in_day_is_not_cheap() -> None:
    start = datetime(2026, 6, 30, 12, 0, tzinfo=ZoneInfo("Europe/London"))
    end = datetime(2026, 6, 30, 12, 30, tzinfo=ZoneInfo("Europe/London"))
    charge = charge_intervals_from_windows("23:30", "05:30", [])
    assert _interval_is_cheap(start, end, charge) is False
