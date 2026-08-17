"""Derive cheap/peak tiers from the user's own Octopus import tariff rates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas.domain import (
    DispatchWindow,
    OctopusRatePlan,
    PlannedCheapWindow,
    RatePlanWindow,
)
from app.services.iog_schedule import minutes_to_time, time_to_minutes
from app.services.tariff_clock import to_tariff


def _rate_at(now: datetime, rates: list[dict[str, Any]]) -> float | None:
    for row in rates:
        start = datetime.fromisoformat(row["valid_from"].replace("Z", "+00:00"))
        if start > now:
            continue
        end_raw = row.get("valid_to")
        if end_raw:
            end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            if end <= now:
                continue
        return float(row["value_inc_vat"])
    return None


def _is_cheap_rate(value: float, cheap_p: float) -> bool:
    return abs(value - cheap_p) < 0.02


def _collapse_daily_windows(minutes: set[int]) -> list[RatePlanWindow]:
    if not minutes:
        return []
    sorted_m = sorted(minutes)
    windows: list[RatePlanWindow] = []
    start = sorted_m[0]
    prev = sorted_m[0]
    for minute in sorted_m[1:]:
        if minute == prev + 30 or (prev == 23 * 60 + 30 and minute == 0):
            prev = minute
            continue
        windows.append(RatePlanWindow(start=minutes_to_time(start), end=minutes_to_time(prev + 30)))
        start = minute
        prev = minute
    windows.append(RatePlanWindow(start=minutes_to_time(start), end=minutes_to_time(prev + 30)))
    return windows


def _windows_from_half_hourly_slots(
    rates: list[dict[str, Any]], cheap_p: float
) -> tuple[list[RatePlanWindow], list[RatePlanWindow]]:
    cheap_minutes: set[int] = set()
    peak_minutes: set[int] = set()
    for row in rates:
        value = float(row["value_inc_vat"])
        start = to_tariff(
            datetime.fromisoformat(row["valid_from"].replace("Z", "+00:00"))
        )
        minute = start.hour * 60 + start.minute
        if _is_cheap_rate(value, cheap_p):
            cheap_minutes.add(minute)
        else:
            peak_minutes.add(minute)
    return _collapse_daily_windows(cheap_minutes), _collapse_daily_windows(peak_minutes)


def _windows_from_offpeak(
    offpeak_start: str, offpeak_end: str
) -> tuple[list[RatePlanWindow], list[RatePlanWindow]]:
    cheap = [RatePlanWindow(start=offpeak_start, end=offpeak_end)]
    start_m = time_to_minutes(offpeak_start)
    end_m = time_to_minutes(offpeak_end)
    if start_m < end_m:
        peak = [
            RatePlanWindow(start=minutes_to_time(end_m), end=offpeak_start),
        ]
    else:
        peak = [RatePlanWindow(start=offpeak_end, end=offpeak_start)]
    return cheap, peak


def _minute_in_windows(minute: int, windows: list[RatePlanWindow]) -> bool:
    for window in windows:
        start = time_to_minutes(window.start)
        end = time_to_minutes(window.end)
        if start < end:
            if start <= minute < end:
                return True
        elif minute >= start or minute < end:
            return True
    return False


def derive_rate_plan(
    rates: list[dict[str, Any]],
    *,
    tariff_family: str,
    region: str,
    import_display_name: str,
    standing_charge_pence: float | None,
    offpeak_start: str,
    offpeak_end: str,
    planned: list[DispatchWindow],
    now: datetime | None = None,
) -> OctopusRatePlan:
    now = now or datetime.now(timezone.utc)
    if not rates:
        return OctopusRatePlan(configured=False)

    values = [float(r["value_inc_vat"]) for r in rates]
    cheap_p = min(values)
    peak_p = max(values)
    current = _rate_at(now, rates)
    current_is_cheap = current is not None and _is_cheap_rate(current, cheap_p)

    unique_slots = len({r["valid_from"] for r in rates})
    if unique_slots >= 4:
        cheap_windows, peak_windows = _windows_from_half_hourly_slots(rates, cheap_p)
    elif cheap_p != peak_p:
        cheap_windows, peak_windows = _windows_from_offpeak(offpeak_start, offpeak_end)
    else:
        cheap_windows = []
        peak_windows = [RatePlanWindow(start="00:00", end="23:30")]

    if cheap_p == peak_p:
        cheap_windows = []
        peak_windows = [RatePlanWindow(start="00:00", end="23:30")]

    now_local = to_tariff(now)
    minute = now_local.hour * 60 + now_local.minute
    if cheap_windows:
        current_is_cheap = _minute_in_windows(minute, cheap_windows)
        if not current_is_cheap:
            for window in planned:
                if window.start <= now < window.end:
                    current_is_cheap = True
                    break

    planned_windows = [
        PlannedCheapWindow(
            start=window.start.isoformat(),
            end=window.end.isoformat(),
            source=window.source or "smart-charge",
        )
        for window in planned
        if window.end > now
    ]

    return OctopusRatePlan(
        configured=True,
        tariff_family=tariff_family,
        region=region,
        import_display_name=import_display_name,
        standing_charge_pence=standing_charge_pence,
        cheap_rate_pence=cheap_p,
        peak_rate_pence=peak_p,
        cheap_windows=cheap_windows,
        peak_windows=peak_windows,
        current_rate_pence=current,
        current_is_cheap=current_is_cheap,
        planned_cheap_windows=planned_windows,
    )
