"""Lookback windows for first-sync vs incremental finance imports."""

from datetime import datetime, timezone

from app.services.finance.sync_lookback import (
    FIRST_SYNC_LOOKBACK_DAYS,
    INCREMENTAL_LOOKBACK_DAYS,
    lookback_days,
    lookback_since,
)


def test_first_sync_lookback_is_365_days() -> None:
    now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    assert lookback_days(first_sync=True) == FIRST_SYNC_LOOKBACK_DAYS
    assert lookback_since(first_sync=True, now=now) == "2025-08-18"


def test_incremental_lookback_is_90_days() -> None:
    now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    assert lookback_days(first_sync=False) == INCREMENTAL_LOOKBACK_DAYS
    assert lookback_since(first_sync=False, now=now) == "2026-05-20"
