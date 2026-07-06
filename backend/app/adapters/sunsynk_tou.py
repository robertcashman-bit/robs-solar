"""Parse Sunsynk Connect inverter settings into TOU bands."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas.domain import SystemWorkMode, TouBand


def _field(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _bool_field(data: dict[str, Any], *keys: str) -> bool:
    raw = _field(data, *keys)
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    return str(raw).lower() in {"true", "1", "yes"}


def _int_field(data: dict[str, Any], key: str) -> int | None:
    raw = data.get(key)
    if raw is None or raw == "":
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _minutes(hhmm: str) -> int:
    hh, mm = hhmm.split(":")
    return int(hh) * 60 + int(mm)


def parse_tou_bands(data: dict[str, Any]) -> list[TouBand]:
    """Build six TOU bands from a Sunsynk settings read payload."""
    starts: list[tuple[int, str]] = []
    for i in range(1, 7):
        start = data.get(f"sellTime{i}")
        if isinstance(start, str) and ":" in start:
            starts.append((i, start))

    bands: list[TouBand] = []
    for idx, (slot, start) in enumerate(starts):
        next_start = starts[idx + 1][1] if idx + 1 < len(starts) else "24:00"
        bands.append(
            TouBand(
                slot=slot,
                start=start,
                end=next_start,
                target_soc_pct=_int_field(data, f"cap{slot}"),
                grid_charge_enabled=_bool_field(data, f"time{slot}on", f"time{slot}On"),
                power_w=_int_field(data, f"sellTime{slot}Pac"),
            )
        )
    return bands


def active_band_index(bands: list[TouBand], now: datetime | None = None) -> int | None:
    if not bands:
        return None
    if now is None:
        from app.services.tariff_clock import tariff_now

        current = tariff_now()
    else:
        from app.services.tariff_clock import to_tariff

        current = to_tariff(now)
    minutes = current.hour * 60 + current.minute
    for band in bands:
        start_m = _minutes(band.start)
        end_m = _minutes(band.end) if band.end != "24:00" else 24 * 60
        if end_m > start_m:
            if start_m <= minutes < end_m:
                return band.slot
        elif minutes >= start_m or minutes < end_m:
            return band.slot
    return bands[-1].slot


def diagnose_battery_hold(bands: list[TouBand], active_slot: int | None) -> str:
    if not bands or active_slot is None:
        return ""
    active = next((b for b in bands if b.slot == active_slot), None)
    if not active:
        return ""
    parts: list[str] = []
    if active.target_soc_pct is not None and active.target_soc_pct >= 90:
        parts.append(f"Cap is {active.target_soc_pct}% on the active band")
    elif active.target_soc_pct is not None:
        parts.append(f"Cap is {active.target_soc_pct}% on the active band")
    if active.grid_charge_enabled:
        parts.append("grid charge is ON (battery may stay topped up instead of discharging)")
    if not parts:
        return "Active band allows discharge; check house load vs solar export settings."
    return " · ".join(parts) + "."


def work_mode_label(sys_work_mode: str | None) -> str:
    mapping = {
        "0": "Limited to home",
        "1": "Limited to home + battery",
        "2": "Selling first",
    }
    if sys_work_mode is None:
        return "Unknown"
    return mapping.get(str(sys_work_mode), f"Mode {sys_work_mode}")


def work_mode_from_sunsynk(sys_work_mode: Any) -> SystemWorkMode | None:
    """Map the Sunsynk ``sysWorkMode`` register to a SystemWorkMode.

    Mirrors the write mapping in SunsynkConnectAdapter.set_operating_mode:
    "0" Limited to home -> bypass/backup, "1" Limited to home + battery ->
    battery first (self-use), "2" Selling first -> selling (feed-in).
    """
    if sys_work_mode is None or str(sys_work_mode).strip() == "":
        return None
    mapping = {
        "0": SystemWorkMode.BYPASS,
        "1": SystemWorkMode.BATTERY_FIRST,
        "2": SystemWorkMode.SELLING,
    }
    return mapping.get(str(sys_work_mode).strip())


def permissions_allow_write(permissions: list[str]) -> bool:
    if not permissions:
        return False
    if any("setting" in p.lower() or "control" in p.lower() for p in permissions):
        return True
    return not all(p.endswith(".view") or p.endswith(".cancle") for p in permissions)
