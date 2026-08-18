"""First-sync vs incremental lookback windows for bank history imports."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# Lunch Flow personal history is capped by the provider (~months of txs). Keep the
# first-sync window at 365 days; widening it does not return older rows.
FIRST_SYNC_LOOKBACK_DAYS = 365
INCREMENTAL_LOOKBACK_DAYS = 90

# QuickFile Bank_Search accepts FromDate/ToDate. A ~10-year pass is reserved for
# explicit force_full=true only — never for live refresh or daily cron.
# Automatic first import uses one year; incremental syncs use ~90 days.
QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS = 3650
QUICKFILE_INITIAL_LOOKBACK_DAYS = 365
QUICKFILE_SATISFIED_LOOKBACK_DAYS = 365
QUICKFILE_LOOKBACK_CHUNK_DAYS = 365

# Neon already has "enough" history to skip an automatic deep import.
QUICKFILE_SUBSTANTIAL_TX_MIN = 100
QUICKFILE_SUBSTANTIAL_SPAN_DAYS = 180


def lookback_since(*, first_sync: bool, now: datetime | None = None) -> str:
    """ISO date for Lunch Flow ``since`` / ``from`` cutoffs."""
    moment = now or datetime.now(timezone.utc)
    days = FIRST_SYNC_LOOKBACK_DAYS if first_sync else INCREMENTAL_LOOKBACK_DAYS
    return (moment - timedelta(days=days)).date().isoformat()


def lookback_days(*, first_sync: bool) -> int:
    return FIRST_SYNC_LOOKBACK_DAYS if first_sync else INCREMENTAL_LOOKBACK_DAYS


def quickfile_lookback_days(
    *,
    first_sync: bool = False,
    force_full: bool = False,
) -> int:
    """QuickFile lookback length.

    - ``force_full`` → ~10 years (explicit Sync ?force_full=true only)
    - ``first_sync`` → ~1 year (empty ledger, non-force import)
    - else → ~90-day incremental (daily cron + normal Sync)
    """
    if force_full:
        return QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS
    if first_sync:
        return QUICKFILE_INITIAL_LOOKBACK_DAYS
    return INCREMENTAL_LOOKBACK_DAYS


def quickfile_lookback_since(
    *,
    first_sync: bool = False,
    force_full: bool = False,
    now: datetime | None = None,
) -> str:
    """ISO date for QuickFile Bank / Invoice / Purchase search cutoffs."""
    moment = now or datetime.now(timezone.utc)
    days = quickfile_lookback_days(first_sync=first_sync, force_full=force_full)
    return (moment - timedelta(days=days)).date().isoformat()


def lookback_date_chunks(
    since: str,
    until: str,
    *,
    chunk_days: int = QUICKFILE_LOOKBACK_CHUNK_DAYS,
) -> list[tuple[str, str]]:
    """Inclusive ISO date windows covering ``since``..``until`` in ``chunk_days`` steps.

    Used so QuickFile searches never ask for a multi-year window in one call. Empty
    older chunks are fine (no history yet); callers still walk the full span.
    """
    if chunk_days < 1:
        raise ValueError("chunk_days must be >= 1")
    start = date.fromisoformat(since[:10])
    end = date.fromisoformat(until[:10])
    if start > end:
        return []
    chunks: list[tuple[str, str]] = []
    cursor = start
    step = timedelta(days=chunk_days)
    while cursor <= end:
        chunk_end = min(cursor + step - timedelta(days=1), end)
        chunks.append((cursor.isoformat(), chunk_end.isoformat()))
        cursor = chunk_end + timedelta(days=1)
    return chunks
