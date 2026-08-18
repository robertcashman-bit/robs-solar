"""Canonical Lunch Flow account identity helpers.

Older rows used ``lunchflow:28085`` + source ``lunch_flow``; newer sync writes
bare ``28085`` + source ``lunchflow``. Treat those as the same real account.
"""

from __future__ import annotations

_PREFIXES = ("lunchflow:", "lunch_flow:")
LUNCHFLOW_SOURCES = frozenset({"lunchflow", "lunch_flow"})


def normalize_lunchflow_external_id(external_id: str | None) -> str:
    """Strip ``lunchflow:`` / ``lunch_flow:`` prefixes; return bare provider id."""
    raw = str(external_id or "").strip()
    if not raw:
        return ""
    lower = raw.casefold()
    for prefix in _PREFIXES:
        if lower.startswith(prefix):
            return raw[len(prefix) :].strip()
    return raw


def lunchflow_external_id_aliases(external_id: str | None) -> frozenset[str]:
    """All stored forms that refer to the same Lunch Flow account."""
    canonical = normalize_lunchflow_external_id(external_id)
    if not canonical:
        return frozenset()
    return frozenset(
        {
            canonical,
            f"lunchflow:{canonical}",
            f"lunch_flow:{canonical}",
        }
    )


def is_lunchflow_source(source: str | None) -> bool:
    return str(source or "").strip().casefold() in LUNCHFLOW_SOURCES
