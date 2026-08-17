"""Snapshot date helpers.

The UI historically posted ``YYYY-MM``. Comparisons and cash-flow dates use
ISO ``YYYY-MM-DD``. Store month-only values as the first day of that month.
"""

from __future__ import annotations

import re

_MONTH_ONLY = re.compile(r"^\d{4}-\d{2}$")


def normalize_snapshot_date(value: str) -> str:
    trimmed = value.strip()
    if _MONTH_ONLY.fullmatch(trimmed):
        return f"{trimmed}-01"
    return trimmed


def snapshot_in_month(snapshot_date: str, month: str) -> bool:
    return snapshot_date == month or snapshot_date.startswith(month)
