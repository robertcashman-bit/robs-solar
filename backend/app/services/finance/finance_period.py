"""Lookback periods for finance read APIs and UI chips.

Historical keys ``1m`` / ``3m`` / ``6m`` are complete calendar months ending
with the previous month. ``mtd`` covers the in-progress current month from day 1
through today (as_of). ``12m`` / ``24m`` are rolling windows through today.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

FinancePeriodKey = Literal["mtd", "1m", "3m", "6m", "12m", "24m"]
FinancePeriodScope = Literal["personal", "business", "both"]

PERIOD_KEYS: tuple[FinancePeriodKey, ...] = ("mtd", "1m", "3m", "6m", "12m", "24m")
PERIOD_MONTHS: dict[str, int] = {
    "mtd": 1,
    "1m": 1,
    "3m": 3,
    "6m": 6,
    "12m": 12,
    "24m": 24,
}
# Rolling keys include the in-progress month through as_of (not end-of-last-month).
ROLLING_THROUGH_TODAY: frozenset[str] = frozenset({"12m", "24m"})
PERIOD_LABELS: dict[str, str] = {
    "mtd": "This month to date",
    "1m": "Last month",
    "3m": "3 months",
    "6m": "6 months",
    "12m": "Last year",
    "24m": "2 years",
}
DEFAULT_PERIOD: FinancePeriodKey = "1m"
DEFAULT_SCOPE: FinancePeriodScope = "personal"


@dataclass(frozen=True)
class PeriodWindow:
    period: str
    label: str
    months_requested: int
    date_from: str
    date_to: str
    month_keys: tuple[str, ...]


def parse_period(raw: str | None, *, default: str = DEFAULT_PERIOD) -> str:
    key = (raw or default).strip().lower()
    if key not in PERIOD_MONTHS:
        raise ValueError(f"Invalid period '{raw}'. Use one of: {', '.join(PERIOD_KEYS)}")
    return key


def parse_scope(raw: str | None, *, default: str = DEFAULT_SCOPE) -> str:
    key = (raw or default).strip().lower()
    if key not in {"personal", "business", "both"}:
        raise ValueError("Invalid scope. Use personal, business, or both")
    return key


def period_label(period: str) -> str:
    return PERIOD_LABELS.get(period, period)


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def _subtract_months(day: date, months: int) -> date:
    year, month = _add_months(day.year, day.month, -months)
    last_day = monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


def _month_keys_inclusive(start: date, end: date) -> tuple[str, ...]:
    keys: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        keys.append(f"{year:04d}-{month:02d}")
        year, month = _add_months(year, month, 1)
    return tuple(keys)


def period_window(period: str, *, as_of: date | None = None) -> PeriodWindow:
    """Return inclusive ISO date bounds for a lookback or month-to-date period."""
    key = parse_period(period)
    today = as_of or datetime.now(timezone.utc).date()
    if key == "mtd":
        date_from = f"{today.year:04d}-{today.month:02d}-01"
        date_to = today.isoformat()
        month_key = f"{today.year:04d}-{today.month:02d}"
        return PeriodWindow(
            period=key,
            label=period_label(key),
            months_requested=1,
            date_from=date_from,
            date_to=date_to,
            month_keys=(month_key,),
        )

    months = PERIOD_MONTHS[key]
    if key in ROLLING_THROUGH_TODAY:
        start = _subtract_months(today, months)
        return PeriodWindow(
            period=key,
            label=period_label(key),
            months_requested=months,
            date_from=start.isoformat(),
            date_to=today.isoformat(),
            month_keys=_month_keys_inclusive(start, today),
        )

    end_year, end_month = _add_months(today.year, today.month, -1)
    start_year, start_month = _add_months(end_year, end_month, -(months - 1))
    date_from = f"{start_year:04d}-{start_month:02d}-01"
    last_day = monthrange(end_year, end_month)[1]
    date_to = f"{end_year:04d}-{end_month:02d}-{last_day:02d}"
    keys: list[str] = []
    year, month = start_year, start_month
    for _ in range(months):
        keys.append(f"{year:04d}-{month:02d}")
        year, month = _add_months(year, month, 1)
    return PeriodWindow(
        period=key,
        label=period_label(key),
        months_requested=months,
        date_from=date_from,
        date_to=date_to,
        month_keys=tuple(keys),
    )


def coverage_note(
    *,
    window: PeriodWindow,
    earliest_posted_on: str | None,
    months_with_data: int,
) -> tuple[bool, str]:
    """Explain partial history without inventing missing months."""
    # Rolling windows touch one more calendar month than months_requested
    # (inclusive mid-month bounds); compare against the actual month_keys span.
    months_in_window = len(window.month_keys)
    if months_with_data <= 0:
        return True, (
            f"No stored transactions in {window.label.lower()} "
            f"({window.date_from} to {window.date_to})."
        )
    if months_with_data < months_in_window:
        earliest = earliest_posted_on or window.date_from
        return (
            True,
            (
                f"Showing available history from {earliest} "
                f"({months_with_data} of {months_in_window} months). "
                f"Requested window starts {window.date_from}."
            ),
        )
    if earliest_posted_on and earliest_posted_on > window.date_from:
        return (
            True,
            (
                f"Showing available history from {earliest_posted_on} "
                f"(requested window starts {window.date_from})."
            ),
        )
    return False, ""
