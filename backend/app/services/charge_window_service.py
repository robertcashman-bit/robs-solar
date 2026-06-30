"""Explain when the inverter imports on purpose during a cheap Octopus window."""

from __future__ import annotations

from datetime import datetime, timezone

from app.adapters.base import InverterAdapter
from app.schemas.domain import ChargeWindowStatus, DispatchWindow, TouBand
from app.services.iog_schedule import (
    charge_intervals_from_windows,
    is_charge_minute,
)
from app.services.octopus_client import octopus_client

_IMPORT_THRESHOLD_W = 50.0
_DISCHARGE_THRESHOLD_W = 100.0


def _local_minute(now: datetime) -> int:
    local = now.astimezone()
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
    local_now = now.astimezone()
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

    importing_on_cheap = cheap_now and holding and importing

    if importing_on_cheap:
        label = "overnight off-peak" if cheap_source == "off-peak" else "smart-charge"
        window_label = f"{window_start}–{window_end}" if window_start and window_end else "now"
        cap_text = f"{target_soc}%" if target_soc is not None else "its target"
        message = (
            f"Importing from the grid on purpose. A cheap Octopus {label} window "
            f"({window_label}) is active, so your battery is held at {cap_text} and "
            "the house runs on cheap grid power to save stored energy for the expensive "
            f"peak rate. Normal battery discharge resumes at {window_end or 'the window end'}."
        )
        return ChargeWindowStatus(
            importing_on_cheap_window=True,
            active=True,
            source=cheap_source or "",
            window_start=window_start,
            window_end=window_end,
            grid_import_w=grid_import_w,
            battery_soc_pct=battery_soc_pct,
            message=message,
        )

    if holding and importing and not cheap_now:
        return ChargeWindowStatus(
            importing_on_cheap_window=False,
            active=True,
            source="unexpected",
            window_start=window_start,
            window_end=window_end,
            grid_import_w=grid_import_w,
            battery_soc_pct=battery_soc_pct,
            message=(
                "The inverter is importing while grid-charge is enabled, but no cheap "
                "Octopus window matches right now. Check the schedule on the Scheduler page."
            ),
        )

    return ChargeWindowStatus(
        importing_on_cheap_window=False,
        active=cheap_now or holding,
        source=cheap_source or "",
        window_start=window_start,
        window_end=window_end,
        grid_import_w=grid_import_w,
        battery_soc_pct=battery_soc_pct,
        message="",
    )


class ChargeWindowService:
    async def get_status(self, adapter: InverterAdapter) -> ChargeWindowStatus:
        try:
            metrics = await adapter.get_live_metrics()
        except Exception:  # noqa: BLE001 — dashboard must not break
            return ChargeWindowStatus(
                importing_on_cheap_window=False,
                active=False,
                message="",
            )

        settings_payload = await adapter.get_inverter_settings()
        active_band = settings_payload.active_band if settings_payload else None

        offpeak_start = "23:30"
        offpeak_end = "05:30"
        planned: list[DispatchWindow] = []
        try:
            if octopus_client.configured():
                dispatches = await octopus_client.get_dispatches()
                offpeak_start = dispatches.off_peak_window.start
                offpeak_end = dispatches.off_peak_window.end
                planned = list(dispatches.planned)
        except Exception:  # noqa: BLE001
            pass

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
