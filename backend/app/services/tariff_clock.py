"""Tariff-timezone clock helpers.

Every cheap/peak window and TOU band boundary must be interpreted in the user's
tariff timezone, never the server's local timezone. A backend deployed in UTC
(Render, Vercel, Docker) would otherwise shift the overnight charge window and
the active daytime band by the UTC offset (one hour during British Summer Time),
which is a real cause of the battery staying charged into the morning instead of
discharging on schedule.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import settings

_FALLBACK = "Europe/London"


def tariff_zone() -> ZoneInfo:
    """Return the configured tariff timezone, falling back to Europe/London."""
    name = (settings.tariff_timezone or "").strip() or _FALLBACK
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return ZoneInfo(_FALLBACK)


def tariff_now() -> datetime:
    """Current time as a tariff-timezone-aware datetime."""
    return datetime.now(tariff_zone())


def to_tariff(moment: datetime | None) -> datetime:
    """Convert any datetime to the tariff timezone.

    Naive datetimes are assumed to be UTC (the app stores timestamps in UTC), so
    a missing tzinfo never silently shifts the wall-clock interpretation.
    """
    moment = moment or tariff_now()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(tariff_zone())


def tariff_minute(moment: datetime | None = None) -> int:
    """Minute-of-day (0-1439) of *moment* in the tariff timezone."""
    local = to_tariff(moment)
    return local.hour * 60 + local.minute
