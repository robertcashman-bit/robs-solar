"""Explain when the inverter imports on purpose during a cheap Octopus window."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.adapters.base import InverterAdapter
from app.config import settings
from app.schemas.domain import ChargeWindowStatus, DispatchWindow, TouBand
from app.services.iog_schedule import (
    charge_intervals_from_windows,
    is_charge_minute,
    time_to_minutes,
)
from app.services.octopus_client import octopus_client
from app.services.tariff_clock import to_tariff

_IMPORT_THRESHOLD_W = 50.0
_DISCHARGE_THRESHOLD_W = 100.0
_FULL_BATTERY_SOC_PCT = 98.0


def _local_minute(now: datetime) -> int:
    local = to_tariff(now)
    return local.hour * 60 + local.minute


def _cheap_source(
    minute: int,
    offpeak_start: str,
    offpeak_end: str,
    planned: list[DispatchWindow],
    *,
    now: datetime,
) -> str | None:
    """Return 'off-peak' or 'smart-charge' if *minute* is inside a cheap window."""
    offpeak_intervals = charge_intervals_from_windows(offpeak_start, offpeak_end, [])
    if is_charge_minute(minute, offpeak_intervals):
        return "off-peak"
    local_now = to_tariff(now)
    for window in planned:
        if window.start <= local_now < window.end:
            return "smart-charge"
    return None


def _is_importing(grid_import_w: float, battery_power_w: float | None) -> bool:
    if grid_import_w <= _IMPORT_THRESHOLD_W:
        return False
    if battery_power_w is None:
        return True
    # Positive batt power = discharging to house; negative = charging from grid.
    return battery_power_w < _DISCHARGE_THRESHOLD_W


def next_cheap_window_start(
    now: datetime,
    offpeak_start: str,
    offpeak_end: str,
    planned: list[DispatchWindow],
) -> tuple[datetime | None, str]:
    """Return the next cheap window start and its source, or (None, '') if cheap now."""
    minute = _local_minute(now)
    intervals = charge_intervals_from_windows(offpeak_start, offpeak_end, planned, now=now)
    if is_charge_minute(minute, intervals):
        return None, ""

    local = to_tariff(now)
    candidates: list[tuple[datetime, str]] = []

    start_min = time_to_minutes(offpeak_start)
    today_offpeak = local.replace(
        hour=start_min // 60,
        minute=start_min % 60,
        second=0,
        microsecond=0,
    )
    if local < today_offpeak:
        candidates.append((today_offpeak, "off-peak"))
    else:
        candidates.append((today_offpeak + timedelta(days=1), "off-peak"))

    for window in planned:
        if window.start > now:
            candidates.append((window.start, "smart-charge"))

    if not candidates:
        return None, ""
    candidates.sort(key=lambda item: item[0])
    return candidates[0]


def _peak_import_message(
    *,
    grid_import_w: float,
    battery_soc_pct: float,
    battery_power_w: float | None,
    holding: bool,
    next_cheap_start: datetime | None,
    next_cheap_source: str,
) -> tuple[str, str, str]:
    import_kw = grid_import_w / 1000.0
    next_hint = ""
    if next_cheap_start is not None:
        local = to_tariff(next_cheap_start)
        label = "off-peak" if next_cheap_source == "off-peak" else "smart-charge"
        next_hint = (
            f" Next cheap {label} window from "
            f"{local.strftime('%H:%M')}."
        )

    if holding:
        return (
            "unexpected",
            "caution",
            "The inverter is importing while grid-charge is enabled, but no cheap "
            "Octopus window matches right now. Check the schedule on the Scheduler page."
            + next_hint,
        )

    if battery_soc_pct >= _FULL_BATTERY_SOC_PCT:
        return (
            "",
            "info",
            f"Importing {import_kw:.1f} kW at the peak day rate. Battery is at "
            f"{battery_soc_pct:.0f}% — extra house load is coming from the grid rather "
            f"than stored energy.{next_hint}",
        )

    if battery_power_w is not None and battery_power_w > _DISCHARGE_THRESHOLD_W:
        return (
            "",
            "info",
            f"Importing {import_kw:.1f} kW at the peak day rate. House load exceeds "
            f"what the battery can supply right now ({battery_power_w:.0f} W "
            "discharging).{next_hint}".replace("{next_hint}", next_hint),
        )

    if battery_power_w is not None and battery_power_w < 0:
        return (
            "",
            "caution",
            f"Importing {import_kw:.1f} kW at the peak day rate while the battery is "
            f"charging from the grid.{next_hint}",
        )

    return (
        "",
        "info",
        f"Importing {import_kw:.1f} kW at the peak day rate.{next_hint}",
    )


def evaluate_charge_window(
    *,
    grid_import_w: float,
    battery_soc_pct: float,
    battery_power_w: float | None,
    active_band: TouBand | None,
    offpeak_start: str,
    offpeak_end: str,
    planned: list[DispatchWindow],
    now: datetime | None = None,
) -> ChargeWindowStatus:
    """Pure decision logic — testable without network or adapter."""
    now = now or datetime.now(timezone.utc)
    minute = _local_minute(now)
    cheap_source = _cheap_source(
        minute,
        offpeak_start,
        offpeak_end,
        planned,
        now=now,
    )
    cheap_now = cheap_source is not None
    holding = bool(active_band and active_band.grid_charge_enabled)
    importing = _is_importing(grid_import_w, battery_power_w)

    window_start = active_band.start if active_band else ""
    window_end = active_band.end if active_band else ""
    target_soc = active_band.target_soc_pct if active_band else None

    next_start, next_source = next_cheap_window_start(
        now, offpeak_start, offpeak_end, planned
    )
    next_cheap_start = next_start.isoformat() if next_start else None

    base = dict(
        cheap_now=cheap_now,
        offpeak_start=offpeak_start,
        offpeak_end=offpeak_end,
        next_cheap_start=next_cheap_start,
        next_cheap_source=next_source or cheap_source or "",
        window_start=window_start,
        window_end=window_end,
        grid_import_w=grid_import_w,
        battery_soc_pct=battery_soc_pct,
        active=cheap_now or holding or importing,
    )

    if cheap_now and importing:
        label = "overnight off-peak" if cheap_source == "off-peak" else "smart-charge"
        cap_text = f"{target_soc}%" if target_soc is not None else "its reserve"
        end_label = offpeak_end if cheap_source == "off-peak" else (
            next(
                (
                    to_tariff(w.end).strftime("%H:%M")
                    for w in planned
                    if w.start <= now < w.end
                ),
                None,
            )
            or window_end
            or "the window end"
        )
        message = (
            f"Importing {grid_import_w / 1000:.1f} kW from the grid on cheap power "
            f"({label}). The battery is held at {cap_text} so stored energy is saved "
            f"for the expensive peak rate. Normal discharge resumes around {end_label}."
        )
        return ChargeWindowStatus(
            **base,
            importing_on_cheap_window=True,
            source=cheap_source or "",
            state="cheap_import",
            severity="good",
            message=message,
        )

    if importing and not cheap_now:
        source, severity, message = _peak_import_message(
            grid_import_w=grid_import_w,
            battery_soc_pct=battery_soc_pct,
            battery_power_w=battery_power_w,
            holding=holding,
            next_cheap_start=next_start,
            next_cheap_source=next_source,
        )
        return ChargeWindowStatus(
            **base,
            importing_on_cheap_window=False,
            source=source,
            state="peak_import",
            severity=severity,
            message=message,
        )

    return ChargeWindowStatus(
        **base,
        importing_on_cheap_window=False,
        source=cheap_source or "",
        state="idle",
        severity="good",
        message="",
    )


class ChargeWindowService:
    async def get_status(self, adapter: InverterAdapter) -> ChargeWindowStatus:
        offpeak_start = settings.iog_offpeak_start
        offpeak_end = settings.iog_offpeak_end
        planned: list[DispatchWindow] = []
        try:
            if octopus_client.configured():
                dispatches = await octopus_client.get_dispatches()
                offpeak_start = dispatches.off_peak_window.start
                offpeak_end = dispatches.off_peak_window.end
                planned = list(dispatches.planned)
        except Exception:  # noqa: BLE001
            pass

        metrics = None
        active_band = None
        try:
            metrics = await adapter.get_live_metrics()
        except Exception:  # noqa: BLE001 — dashboard must not break
            pass

        try:
            settings_payload = await adapter.get_inverter_settings()
            active_band = settings_payload.active_band if settings_payload else None
        except Exception:  # noqa: BLE001
            pass

        if metrics is None:
            return ChargeWindowStatus(
                cheap_now=_cheap_source(
                    _local_minute(datetime.now(timezone.utc)),
                    offpeak_start,
                    offpeak_end,
                    planned,
                    now=datetime.now(timezone.utc),
                )
                is not None,
                offpeak_start=offpeak_start,
                offpeak_end=offpeak_end,
                active=False,
                message="",
            )

        return evaluate_charge_window(
            grid_import_w=metrics.grid_import_w,
            battery_soc_pct=metrics.battery_soc_pct,
            battery_power_w=metrics.battery_power_w,
            active_band=active_band,
            offpeak_start=offpeak_start,
            offpeak_end=offpeak_end,
            planned=planned,
        )


charge_window_service = ChargeWindowService()
