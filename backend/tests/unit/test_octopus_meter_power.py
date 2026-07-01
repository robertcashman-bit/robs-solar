"""Unit tests for Octopus smart-meter average power from half-hourly intervals."""

from datetime import datetime, timezone

from app.services.octopus_client import (
    consumption_average_power_w,
    pick_consumption_interval_for_display,
)


def test_consumption_average_power_w_half_hour() -> None:
    start = datetime(2026, 7, 1, 19, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 1, 19, 30, tzinfo=timezone.utc)
    assert consumption_average_power_w(0.188, start, end) == 376.0


def test_pick_consumption_interval_prefers_current_half_hour() -> None:
    now = datetime(2026, 7, 1, 19, 15, tzinfo=timezone.utc)
    intervals = [
        {
            "interval_start": "2026-07-01T19:00:00Z",
            "interval_end": "2026-07-01T19:30:00Z",
            "consumption": 0.188,
        },
        {
            "interval_start": "2026-07-01T18:30:00Z",
            "interval_end": "2026-07-01T19:00:00Z",
            "consumption": 0.12,
        },
    ]
    picked = pick_consumption_interval_for_display(intervals, now=now)
    assert picked is not None
    start, end, kwh, is_current = picked
    assert is_current is True
    assert kwh == 0.188
    assert consumption_average_power_w(kwh, start, end) == 376.0


def test_pick_consumption_interval_uses_latest_completed_when_between_slots() -> None:
    now = datetime(2026, 7, 1, 19, 35, tzinfo=timezone.utc)
    intervals = [
        {
            "interval_start": "2026-07-01T19:30:00Z",
            "interval_end": "2026-07-01T20:00:00Z",
            "consumption": 0.05,
        },
        {
            "interval_start": "2026-07-01T19:00:00Z",
            "interval_end": "2026-07-01T19:30:00Z",
            "consumption": 0.188,
        },
    ]
    picked = pick_consumption_interval_for_display(intervals, now=now)
    assert picked is not None
    _, _, kwh, is_current = picked
    assert is_current is True
    assert kwh == 0.05
