"""Shared analytics helpers (avoids circular imports between services)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.models import MetricSampleRow
from app.schemas.domain import HistoryRange
from app.services.iog_schedule import charge_intervals_from_windows, is_charge_minute
from app.services.tariff_clock import tariff_now, to_tariff


def range_start(range_name: HistoryRange) -> datetime:
    now = datetime.now(timezone.utc)
    if range_name == HistoryRange.DAY:
        local_midnight = tariff_now().replace(hour=0, minute=0, second=0, microsecond=0)
        return local_midnight.astimezone(timezone.utc)
    if range_name == HistoryRange.WEEK:
        return now - timedelta(days=7)
    if range_name == HistoryRange.MONTH:
        return now - timedelta(days=30)
    return now - timedelta(days=365)


def integrate_kwh(rows: list[MetricSampleRow], field: str) -> float:
    if len(rows) < 2:
        return 0.0
    total_wh = 0.0
    for prev, curr in zip(rows, rows[1:]):
        dt_hours = (curr.timestamp - prev.timestamp).total_seconds() / 3600.0
        if dt_hours <= 0:
            continue
        p1 = getattr(prev, field)
        p2 = getattr(curr, field)
        total_wh += (p1 + p2) / 2.0 * dt_hours
    return total_wh / 1000.0


def split_import_kwh(
    rows: list[MetricSampleRow],
    off_peak_start: str,
    off_peak_end: str,
) -> tuple[float, float]:
    if len(rows) < 2:
        return 0.0, integrate_kwh(rows, "grid_import_w")
    intervals = charge_intervals_from_windows(off_peak_start, off_peak_end, [])
    cheap_wh = 0.0
    peak_wh = 0.0
    for prev, curr in zip(rows, rows[1:]):
        dt_hours = (curr.timestamp - prev.timestamp).total_seconds() / 3600.0
        if dt_hours <= 0:
            continue
        avg_w = (prev.grid_import_w + curr.grid_import_w) / 2.0
        if avg_w <= 0:
            continue
        local = to_tariff(curr.timestamp)
        minute = local.hour * 60 + local.minute
        wh = avg_w * dt_hours
        if is_charge_minute(minute, intervals):
            cheap_wh += wh
        else:
            peak_wh += wh
    return cheap_wh / 1000.0, peak_wh / 1000.0
