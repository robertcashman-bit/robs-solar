"""First-sync vs incremental lookback windows for bank history imports."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# Align Lunch Flow first-sync lookback with QuickFile (~730 days). The provider
# may still return fewer months; fingerprints dedupe. Daily incremental stays
# at 90 days — the safe incremental window.
FIRST_SYNC_LOOKBACK_DAYS = 730
INCREMENTAL_LOOKBACK_DAYS = 90

# QuickFile Bank_Search accepts FromDate/ToDate. A ~2-year pass is used for
# force_full=true (Settings retry or daily cron when lookback is still short).
# Live dashboard refresh never uses this path. Automatic first import (empty
# ledger) uses one year; normal incremental syncs use ~90 days.
QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS = 730
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

    - ``force_full`` → ~2 years (Settings Import full history, or daily cron
      when stored lookback is missing / shorter than this window)
    - ``first_sync`` → ~1 year (empty ledger, non-force import)
    - else → ~90-day incremental (daily cron after 2-year import + normal Sync)
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
