"""Validation for the battery charge/discharge schedule configuration.

These checks exist to prevent the "battery stuck near full all day" failure
mode: a daytime reserve set too high, an overnight target below the reserve, a
missing/invalid tariff timezone, or a degenerate cheap-rate window.
"""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# A daytime reserve at or above this would effectively hold the battery full and
# force grid import during the day. Reject it outright.
HARD_MAX_DAYTIME_FLOOR_PCT = 95


@dataclass(frozen=True)
class ScheduleIssue:
    level: str  # "error" | "warning"
    code: str
    message: str


def validate_schedule_config(
    *,
    daytime_floor_pct: int,
    overnight_target_pct: int,
    offpeak_start: str,
    offpeak_end: str,
    tariff_timezone: str,
    daytime_discharge_enabled: bool = True,
    max_daytime_floor_pct: int = 90,
) -> list[ScheduleIssue]:
    issues: list[ScheduleIssue] = []

    if not 0 <= daytime_floor_pct <= 100:
        issues.append(
            ScheduleIssue(
                "error",
                "floor_out_of_range",
                f"Daytime reserve {daytime_floor_pct}% must be between 0 and 100.",
            )
        )
    elif daytime_floor_pct >= HARD_MAX_DAYTIME_FLOOR_PCT:
        issues.append(
            ScheduleIssue(
                "error",
                "floor_too_high",
                f"Daytime reserve {daytime_floor_pct}% would keep the battery effectively "
                "full all day and force grid import. Set it well below 95% (e.g. 20%).",
            )
        )
    elif daytime_floor_pct > max_daytime_floor_pct:
        issues.append(
            ScheduleIssue(
                "warning",
                "floor_high",
                f"Daytime reserve {daytime_floor_pct}% is high; the battery will only "
                "discharge a little before holding. Consider a lower reserve such as 20%.",
            )
        )

    if not 0 <= overnight_target_pct <= 100:
        issues.append(
            ScheduleIssue(
                "error",
                "target_out_of_range",
                f"Overnight target {overnight_target_pct}% must be between 0 and 100.",
            )
        )
    elif overnight_target_pct <= daytime_floor_pct:
        issues.append(
            ScheduleIssue(
                "error",
                "target_below_floor",
                f"Overnight charge target {overnight_target_pct}% must be above the daytime "
                f"reserve {daytime_floor_pct}%, otherwise there is nothing to discharge.",
            )
        )

    try:
        ZoneInfo((tariff_timezone or "").strip())
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        issues.append(
            ScheduleIssue(
                "error",
                "bad_timezone",
                f"Tariff timezone '{tariff_timezone}' is not a valid IANA zone "
                "(e.g. 'Europe/London').",
            )
        )

    if not _valid_hhmm(offpeak_start) or not _valid_hhmm(offpeak_end):
        issues.append(
            ScheduleIssue(
                "error",
                "bad_window",
                f"Off-peak window {offpeak_start}-{offpeak_end} must use HH:MM times.",
            )
        )
    elif offpeak_start == offpeak_end:
        issues.append(
            ScheduleIssue(
                "warning",
                "window_full_day",
                "Off-peak start and end are identical, which is treated as charging all "
                "day. Set distinct start/end times.",
            )
        )

    if not daytime_discharge_enabled:
        issues.append(
            ScheduleIssue(
                "warning",
                "discharge_disabled",
                "Daytime battery discharge is disabled, so the house will import from the "
                "grid during the day instead of using stored energy.",
            )
        )

    return issues


def _valid_hhmm(value: str) -> bool:
    try:
        hh, mm = value.split(":")
        return 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59
    except (AttributeError, ValueError):
        return False


def errors_only(issues: list[ScheduleIssue]) -> list[ScheduleIssue]:
    return [i for i in issues if i.level == "error"]
