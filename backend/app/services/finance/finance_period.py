"""Historical lookback periods for finance read APIs and UI chips.

Periods are complete calendar months ending with the previous month
(so "last month" is never the in-progress current month).
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

FinancePeriodKey = Literal["1m", "3m", "6m", "12m"]
FinancePeriodScope = Literal["personal", "business", "both"]

PERIOD_KEYS: tuple[FinancePeriodKey, ...] = ("1m", "3m", "6m", "12m")
PERIOD_MONTHS: dict[str, int] = {"1m": 1, "3m": 3, "6m": 6, "12m": 12}
PERIOD_LABELS: dict[str, str] = {
    "1m": "Last month",
    "3m": "3 months",
    "6m": "6 months",
    "12m": "Last year",
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


def period_window(period: str, *, as_of: date | None = None) -> PeriodWindow:
    """Return inclusive ISO date bounds for a historical lookback period."""
    key = parse_period(period)
    months = PERIOD_MONTHS[key]
    today = as_of or datetime.now(timezone.utc).date()
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
    if months_with_data <= 0:
        return True, (
            f"No stored transactions in {window.label.lower()} "
            f"({window.date_from} to {window.date_to})."
        )
    if months_with_data < window.months_requested:
        earliest = earliest_posted_on or window.date_from
        return (
            True,
            (
                f"Showing available history from {earliest} "
                f"({months_with_data} of {window.months_requested} months). "
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
