"""Pure IOG schedule logic — compute Sunsynk TOU bands from cheap windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.schemas.domain import DispatchWindow, TouBandWrite
from app.services.tariff_clock import to_tariff


def time_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def minutes_to_time(value: int) -> str:
    value = value % (24 * 60)
    return f"{value // 60:02d}:{value % 60:02d}"


def expand_interval(start: int, end: int) -> list[tuple[int, int]]:
    """Expand an interval on the 24h clock; split if it wraps midnight."""
    start = start % (24 * 60)
    end = end % (24 * 60)
    if start == end:
        return [(0, 24 * 60)]
    if start < end:
        return [(start, end)]
    return [(start, 24 * 60), (0, end)]


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    flat: list[tuple[int, int]] = []
    for start, end in intervals:
        flat.extend(expand_interval(start, end))
    flat.sort(key=lambda item: item[0])
    merged: list[tuple[int, int]] = []
    for start, end in flat:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])  # type: ignore[list-item]
        else:
            merged[-1][1] = max(merged[-1][1], end)  # type: ignore[index]
    return [(s, e) for s, e in merged]


def interval_overlaps_offpeak(
    start_minute: int,
    end_minute: int,
    offpeak_start: str,
    offpeak_end: str,
) -> bool:
    """True when any part of [start, end) overlaps the configured off-peak window."""
    off_start = time_to_minutes(offpeak_start)
    off_end = time_to_minutes(offpeak_end)
    for seg_start, seg_end in expand_interval(start_minute, end_minute):
        for off_s, off_e in expand_interval(off_start, off_end):
            if seg_start < off_e and off_s < seg_end:
                return True
    return False


def charge_intervals_from_windows(
    offpeak_start: str,
    offpeak_end: str,
    planned: list[DispatchWindow],
    *,
    now: datetime | None = None,
) -> list[tuple[int, int]]:
    """Build merged charge intervals from IOG off-peak + future planned dispatches."""
    now = now or datetime.now(timezone.utc)
    intervals: list[tuple[int, int]] = expand_interval(
        time_to_minutes(offpeak_start),
        time_to_minutes(offpeak_end),
    )
    for window in planned:
        if window.end <= now:
            continue
        local_start = to_tariff(window.start).strftime("%H:%M")
        local_end = to_tariff(window.end).strftime("%H:%M")
        start_m = time_to_minutes(local_start)
        end_m = time_to_minutes(local_end)
        # Skip peak-only smart-charge windows — they create daytime grid-charge bands
        # that block battery discharge and cause expensive peak import.
        if not interval_overlaps_offpeak(start_m, end_m, offpeak_start, offpeak_end):
            continue
        intervals.extend(expand_interval(start_m, end_m))
    return merge_intervals(intervals)


def is_charge_minute(minute: int, charge_intervals: list[tuple[int, int]]) -> bool:
    for start, end in charge_intervals:
        if start <= minute < end:
            return True
    return False


@dataclass(frozen=True)
class ScheduleSegment:
    start_minute: int
    charge: bool


def segments_from_charge_intervals(
    charge_intervals: list[tuple[int, int]],
) -> list[ScheduleSegment]:
    """Walk the day and produce alternating charge/discharge segments."""
    boundaries = {0, 24 * 60}
    for start, end in charge_intervals:
        boundaries.add(start)
        boundaries.add(end)
    ordered = sorted(boundaries)
    segments: list[ScheduleSegment] = []
    for idx in range(len(ordered) - 1):
        start = ordered[idx]
        end = ordered[idx + 1]
        if start == end:
            continue
        mid = (start + end) // 2
        segments.append(
            ScheduleSegment(
                start_minute=start,
                charge=is_charge_minute(mid, charge_intervals),
            )
        )
    return segments


def merge_adjacent_segments(segments: list[ScheduleSegment]) -> list[ScheduleSegment]:
    if not segments:
        return []
    merged: list[ScheduleSegment] = [segments[0]]
    for segment in segments[1:]:
        if segment.charge == merged[-1].charge:
            continue
        merged.append(segment)
    return merged


def collapse_to_six(segments: list[ScheduleSegment]) -> list[ScheduleSegment]:
    """Ensure at most six segments by dropping smallest charge islands if needed."""
    merged = merge_adjacent_segments(segments)
    while len(merged) > 6:
        # Drop the shortest charge segment (usually a small bonus dispatch).
        charge_indices = [i for i, seg in enumerate(merged) if seg.charge]
        if not charge_indices:
            break
        shortest_idx = min(
            charge_indices,
            key=lambda i: (
                merged[i + 1].start_minute - merged[i].start_minute
                if i + 1 < len(merged)
                else (24 * 60 - merged[i].start_minute)
            ),
        )
        merged.pop(shortest_idx)
    return merged[:6]


def segments_to_bands(
    segments: list[ScheduleSegment],
    *,
    soc_floor_pct: int,
    overnight_target_pct: int = 100,
    charge_power_w: int = 8000,
    discharge_power_w: int = 8000,
) -> list[TouBandWrite]:
    """Turn charge/discharge segments into Sunsynk TOU bands.

    Charge segments (cheap window): grid charge ON, cap = overnight target so the
    battery fills up. Discharge segments (daytime): grid charge OFF and cap = the
    daytime floor so the inverter discharges stored energy down to the reserve
    instead of holding the battery full and importing from the grid.
    """
    bands: list[TouBandWrite] = []
    for slot, segment in enumerate(segments, start=1):
        bands.append(
            TouBandWrite(
                slot=slot,
                start=minutes_to_time(segment.start_minute),
                target_soc_pct=overnight_target_pct if segment.charge else soc_floor_pct,
                grid_charge_enabled=segment.charge,
                power_w=charge_power_w if segment.charge else discharge_power_w,
            )
        )
    return bands


def pad_bands_to_six(
    bands: list[TouBandWrite],
    *,
    soc_floor_pct: int,
    discharge_power_w: int = 8000,
) -> list[TouBandWrite]:
    """Ensure six Sunsynk slots are defined; unused slots stay on safe daytime discharge."""
    if not bands:
        return bands
    discharge_template = next(
        (b for b in reversed(bands) if not b.grid_charge_enabled),
        bands[-1],
    )
    by_slot = {band.slot: band for band in bands}
    used_starts = {band.start for band in bands}
    filler_starts = ["06:00", "12:00", "18:00", "08:00", "14:00", "20:00"]
    filler_iter = iter(start for start in filler_starts if start not in used_starts)
    padded: list[TouBandWrite] = []
    for slot in range(1, 7):
        if slot in by_slot:
            padded.append(by_slot[slot])
            continue
        start = next(filler_iter, discharge_template.start)
        while start in used_starts:
            try:
                start = next(filler_iter)
            except StopIteration:
                start = discharge_template.start
                break
        used_starts.add(start)
        padded.append(
            TouBandWrite(
                slot=slot,
                start=start,
                target_soc_pct=soc_floor_pct,
                grid_charge_enabled=False,
                power_w=discharge_power_w,
            )
        )
    return padded


def compute_iog_bands(
    *,
    offpeak_start: str,
    offpeak_end: str,
    planned: list[DispatchWindow],
    soc_floor_pct: int,
    overnight_target_pct: int = 100,
    now: datetime | None = None,
) -> list[TouBandWrite]:
    charge = charge_intervals_from_windows(offpeak_start, offpeak_end, planned, now=now)
    segments = segments_from_charge_intervals(charge)
    collapsed = collapse_to_six(segments)
    bands = segments_to_bands(
        collapsed,
        soc_floor_pct=soc_floor_pct,
        overnight_target_pct=overnight_target_pct,
    )
    for idx, band in enumerate(bands, start=1):
        band.slot = idx
    return pad_bands_to_six(bands, soc_floor_pct=soc_floor_pct)


def bands_equivalent(
    desired: list[TouBandWrite],
    current: list[TouBandWrite],
) -> bool:
    if len(desired) != len(current):
        return False
    for left, right in zip(desired, current):
        if (
            left.start != right.start
            or left.target_soc_pct != right.target_soc_pct
            or left.grid_charge_enabled != right.grid_charge_enabled
        ):
            return False
    return True
