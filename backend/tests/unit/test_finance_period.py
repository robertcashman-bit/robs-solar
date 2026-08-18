"""Unit tests for historical period parsing and lookback windows."""

from datetime import date

import pytest

from app.services.finance.finance_period import (
    coverage_note,
    parse_period,
    parse_scope,
    period_window,
)


def test_parse_period_accepts_known_keys() -> None:
    assert parse_period("1m") == "1m"
    assert parse_period("3M") == "3m"
    assert parse_period("mtd") == "mtd"
    assert parse_period("MTD") == "mtd"
    assert parse_period(None) == "1m"


def test_parse_period_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Invalid period"):
        parse_period("2m")


def test_period_window_mtd_includes_current_month_through_today() -> None:
    window = period_window("mtd", as_of=date(2026, 8, 18))
    assert window.date_from == "2026-08-01"
    assert window.date_to == "2026-08-18"
    assert window.month_keys == ("2026-08",)
    assert window.months_requested == 1
    assert window.label == "This month to date"


def test_parse_scope_accepts_personal_business_both() -> None:
    assert parse_scope("personal") == "personal"
    assert parse_scope("BUSINESS") == "business"
    assert parse_scope("both") == "both"


def test_parse_scope_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Invalid scope"):
        parse_scope("household")


def test_period_window_last_month_excludes_current_month() -> None:
    window = period_window("1m", as_of=date(2026, 8, 18))
    assert window.date_from == "2026-07-01"
    assert window.date_to == "2026-07-31"
    assert window.month_keys == ("2026-07",)
    assert window.label == "Last month"


def test_period_window_three_months() -> None:
    window = period_window("3m", as_of=date(2026, 8, 18))
    assert window.date_from == "2026-05-01"
    assert window.date_to == "2026-07-31"
    assert window.month_keys == ("2026-05", "2026-06", "2026-07")
    assert window.months_requested == 3


def test_period_window_year_crosses_year_boundary() -> None:
    window = period_window("12m", as_of=date(2026, 3, 10))
    assert window.date_from == "2025-03-01"
    assert window.date_to == "2026-02-28"
    assert len(window.month_keys) == 12


def test_coverage_note_marks_partial_history() -> None:
    window = period_window("6m", as_of=date(2026, 8, 18))
    partial, note = coverage_note(
        window=window,
        earliest_posted_on="2026-05-12",
        months_with_data=3,
    )
    assert partial is True
    assert "3 of 6 months" in note
    assert "2026-05-12" in note
