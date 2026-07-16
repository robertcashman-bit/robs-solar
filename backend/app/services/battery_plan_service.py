"""Aggregate the full battery charge/discharge decision picture for diagnostics.

This powers GET /metrics/battery-plan, the single screen that explains *why* the
battery is or is not discharging right now: tariff period, live power flows, the
real inverter mode, the active TOU band reserve, whether writes are enabled, the
last command sent, and any configuration issues.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import InverterAdapter
from app.config import settings
from app.schemas.domain import (
    BatteryPlanStatus,
    ScheduleIssueModel,
)
from app.services.auto_schedule_service import auto_schedule_service
from app.services.charge_window_service import charge_window_service
from app.services.octopus_client import octopus_client
from app.services.safety_settings_service import safety_settings_service
from app.services.schedule_validation import validate_schedule_config
from app.services.tariff_clock import tariff_now

logger = logging.getLogger(__name__)

_IMPORT_W = 50.0
_DISCHARGE_W = 100.0


class BatteryPlanService:
    async def get_plan(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
    ) -> BatteryPlanStatus:
        now_local = tariff_now()

        window = await charge_window_service.get_status(adapter)

        metrics = None
        try:
            metrics = await adapter.get_live_metrics()
        except Exception:  # noqa: BLE001 — diagnostics must never crash
            logger.warning("Battery plan: failed to load live metrics", exc_info=True)

        settings_payload = None
        try:
            settings_payload = await adapter.get_inverter_settings()
        except Exception:  # noqa: BLE001
            logger.warning("Battery plan: failed to load inverter settings", exc_info=True)

        auto_config = await auto_schedule_service._load_config(db)
        auto_enabled = bool(auto_config.get("enabled", False))
        floor = int(auto_config.get("soc_floor_pct", settings.auto_schedule_soc_floor_pct))
        target = int(
            auto_config.get("overnight_target_pct", settings.auto_schedule_overnight_target_pct)
        )
        auto_status = await auto_schedule_service.get_status(db)

        writes_enabled = (
            not safety_settings_service.effective_read_only()
            and safety_settings_service.effective_enable_live_writes()
        )
        write_allowed = bool(getattr(settings_payload, "write_allowed", False))

        soc = metrics.battery_soc_pct if metrics else window.battery_soc_pct
        batt_power = metrics.battery_power_w if metrics else None
        pv = metrics.pv_power_w if metrics else 0.0
        load = metrics.house_load_w if metrics else 0.0
        grid_import = metrics.grid_import_w if metrics else window.grid_import_w
        grid_export = metrics.grid_export_w if metrics else 0.0

        battery_flow = self._battery_flow(batt_power)
        grid_flow = self._grid_flow(grid_import, grid_export)

        active = getattr(settings_payload, "active_band", None)
        active_cap = getattr(active, "target_soc_pct", None)
        active_grid_charge = bool(getattr(active, "grid_charge_enabled", False))
        active_start = getattr(active, "start", "") or ""

        offpeak_start = settings.iog_offpeak_start
        offpeak_end = settings.iog_offpeak_end
        try:
            if octopus_client.configured():
                dispatches = await octopus_client.get_dispatches()
                offpeak_start = dispatches.off_peak_window.start
                offpeak_end = dispatches.off_peak_window.end
        except Exception:  # noqa: BLE001
            logger.warning("Battery plan: failed to load Octopus dispatches", exc_info=True)

        issues = [
            ScheduleIssueModel(level=i.level, code=i.code, message=i.message)
            for i in validate_schedule_config(
                daytime_floor_pct=floor,
                overnight_target_pct=target,
                offpeak_start=offpeak_start,
                offpeak_end=offpeak_end,
                tariff_timezone=settings.tariff_timezone,
                max_daytime_floor_pct=settings.max_daytime_floor_pct,
            )
        ]

        blocked = self._discharge_blocked_reason(
            cheap_now=window.cheap_now,
            soc=soc,
            floor=floor,
            active_cap=active_cap,
            active_grid_charge=active_grid_charge,
            auto_enabled=auto_enabled,
            writes_enabled=writes_enabled,
            write_allowed=write_allowed,
            grid_import=grid_import,
            batt_power=batt_power,
        )

        summary = self._summary(
            cheap_now=window.cheap_now,
            battery_flow=battery_flow,
            grid_flow=grid_flow,
            blocked=blocked,
            soc=soc,
            floor=floor,
        )

        return BatteryPlanStatus(
            timestamp=now_local,
            tariff_timezone=settings.tariff_timezone,
            tariff_local_time=now_local.strftime("%Y-%m-%d %H:%M %Z"),
            tariff_period="cheap" if window.cheap_now else "peak",
            pv_power_w=pv,
            house_load_w=load,
            grid_import_w=grid_import,
            grid_export_w=grid_export,
            battery_soc_pct=soc,
            battery_power_w=batt_power,
            battery_flow=battery_flow,
            grid_flow=grid_flow,
            inverter_mode=(metrics.inverter_mode.value if metrics else ""),
            sys_work_mode_label=getattr(settings_payload, "sys_work_mode_label", "") or "",
            daytime_floor_pct=floor,
            overnight_target_pct=target,
            daytime_discharge_enabled=auto_enabled,
            active_band_start=active_start,
            active_band_cap_pct=active_cap,
            active_band_grid_charge=active_grid_charge,
            auto_align_enabled=auto_enabled,
            writes_enabled=writes_enabled,
            write_allowed=write_allowed,
            discharge_blocked_reason=blocked,
            last_command=auto_status.last_run_message,
            last_command_at=auto_status.last_run_at,
            last_write_audit_id=auto_status.last_write_audit_id,
            next_cheap_start=window.next_cheap_start,
            issues=issues,
            summary=summary,
        )

    @staticmethod
    def _battery_flow(batt_power: float | None) -> str:
        if batt_power is None:
            return "idle"
        if batt_power > _DISCHARGE_W:
            return "discharging"
        if batt_power < -_DISCHARGE_W:
            return "charging"
        return "idle"

    @staticmethod
    def _grid_flow(grid_import: float, grid_export: float) -> str:
        if grid_import > _IMPORT_W:
            return "importing"
        if grid_export > _IMPORT_W:
            return "exporting"
        return "idle"

    @staticmethod
    def _discharge_blocked_reason(
        *,
        cheap_now: bool,
        soc: float,
        floor: int,
        active_cap: int | None,
        active_grid_charge: bool,
        auto_enabled: bool,
        writes_enabled: bool,
        write_allowed: bool,
        grid_import: float,
        batt_power: float | None,
    ) -> str:
        if cheap_now:
            return ""  # intentionally charging/holding on cheap rate
        if soc <= floor + 1:
            return f"Battery is at its {floor}% reserve, so discharge has stopped (expected)."
        # Only flag a real problem when we are actually importing and not discharging.
        importing_not_discharging = grid_import > _IMPORT_W and (
            batt_power is None or batt_power < _DISCHARGE_W
        )
        if not importing_not_discharging:
            return ""
        if active_cap is not None and active_cap >= soc:
            return (
                f"Active TOU band reserve is {active_cap}% which is at/above the current "
                f"SOC {soc:.0f}%, so the inverter holds the battery instead of discharging."
            )
        if active_grid_charge:
            return (
                "Grid charge is ON for the active band, so the inverter keeps the battery "
                "topped up from the grid instead of discharging."
            )
        if auto_enabled and not writes_enabled:
            return (
                "Auto-align is enabled but live writes are disabled, so the daytime "
                "discharge schedule is never sent to the inverter. Enable live writes."
            )
        if auto_enabled and not write_allowed:
            return (
                "Auto-align is enabled but the Sunsynk account lacks write permission, so "
                "the daytime discharge schedule cannot be applied."
            )
        if not auto_enabled:
            return (
                "Auto-align is off, so the app is not managing the daytime discharge floor; "
                "the inverter is using its own schedule."
            )
        return ""

    @staticmethod
    def _summary(
        *,
        cheap_now: bool,
        battery_flow: str,
        grid_flow: str,
        blocked: str,
        soc: float,
        floor: int,
    ) -> str:
        parts: list[str] = []
        if battery_flow == "discharging":
            parts.append("Battery is discharging to cover the house load.")
        elif battery_flow == "charging":
            parts.append("Battery is charging.")
        if grid_flow == "importing":
            parts.append("Importing from the grid.")
        elif grid_flow == "exporting":
            parts.append("Exporting to the grid.")
        if cheap_now:
            parts.append("Cheap-rate window: charging/holding is intended.")
        if blocked:
            parts.append(blocked)
        if not parts:
            parts.append(f"Battery at {soc:.0f}% (reserve {floor}%).")
        return " ".join(parts)


battery_plan_service = BatteryPlanService()
