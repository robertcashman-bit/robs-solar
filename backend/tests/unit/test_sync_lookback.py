"""Lookback windows for first-sync vs incremental finance imports."""

from datetime import datetime, timezone

from app.services.finance.sync_lookback import (
    FIRST_SYNC_LOOKBACK_DAYS,
    INCREMENTAL_LOOKBACK_DAYS,
    QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS,
    QUICKFILE_INITIAL_LOOKBACK_DAYS,
    lookback_date_chunks,
    lookback_days,
    lookback_since,
    quickfile_lookback_days,
    quickfile_lookback_since,
)


def test_first_sync_lookback_is_365_days() -> None:
    now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    assert lookback_days(first_sync=True) == FIRST_SYNC_LOOKBACK_DAYS
    assert lookback_since(first_sync=True, now=now) == "2025-08-18"


def test_incremental_lookback_is_90_days() -> None:
    now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    assert lookback_days(first_sync=False) == INCREMENTAL_LOOKBACK_DAYS
    assert lookback_since(first_sync=False, now=now) == "2026-05-20"


def test_quickfile_initial_lookback_is_one_year() -> None:
    now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    assert quickfile_lookback_days(first_sync=True) == QUICKFILE_INITIAL_LOOKBACK_DAYS
    assert quickfile_lookback_since(first_sync=True, now=now) == "2025-08-18"
    assert quickfile_lookback_since(first_sync=False, now=now) == "2026-05-20"


def test_quickfile_force_full_lookback_is_about_ten_years() -> None:
    now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    assert quickfile_lookback_days(force_full=True) == QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS
    assert QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS >= 5 * 365
    assert quickfile_lookback_since(force_full=True, now=now) == "2016-08-20"


def test_lookback_date_chunks_cover_range_in_year_windows() -> None:
    chunks = lookback_date_chunks("2024-01-01", "2026-08-18", chunk_days=365)
    assert chunks[0] == ("2024-01-01", "2024-12-30")
    assert chunks[1] == ("2024-12-31", "2025-12-30")
    assert chunks[-1][1] == "2026-08-18"
    # Contiguous and non-overlapping.
    for left, right in zip(chunks, chunks[1:]):
        assert left[1] < right[0]


def test_lookback_date_chunks_single_short_window() -> None:
    assert lookback_date_chunks("2026-05-20", "2026-08-18", chunk_days=365) == [
        ("2026-05-20", "2026-08-18")
    ]


def test_lookback_date_chunks_empty_when_inverted() -> None:
    assert lookback_date_chunks("2026-08-18", "2026-01-01") == []
