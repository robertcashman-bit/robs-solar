"""First-sync vs incremental lookback windows for bank history imports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Lunch Flow / QuickFile Bank_Search support ~365 days of history.
# Incremental windows stay short so daily cron stays cheap; fingerprints dedupe overlap.
FIRST_SYNC_LOOKBACK_DAYS = 365
INCREMENTAL_LOOKBACK_DAYS = 90


def lookback_since(*, first_sync: bool, now: datetime | None = None) -> str:
    """ISO date for provider ``since`` / ``from`` cutoffs."""
    moment = now or datetime.now(timezone.utc)
    days = FIRST_SYNC_LOOKBACK_DAYS if first_sync else INCREMENTAL_LOOKBACK_DAYS
    return (moment - timedelta(days=days)).date().isoformat()


def lookback_days(*, first_sync: bool) -> int:
    return FIRST_SYNC_LOOKBACK_DAYS if first_sync else INCREMENTAL_LOOKBACK_DAYS
