"""Auto-align Sunsynk TOU bands to IOG cheap windows."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import InverterAdapter
from app.adapters.sunsynk_tou import work_mode_from_sunsynk
from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.domain import (
    AutoScheduleConfigRequest,
    AutoScheduleStatus,
    DispatchWindow,
    InverterMode,
    InverterSettingsResponse,
    OperatingModeRequest,
    TouBandsRequest,
    TouBandWrite,
    UserRole,
)
from app.services.charge_window_service import evaluate_charge_window
from app.services.control_service import control_service
from app.services.ev_load_detector import ev_load_detector
from app.services.iog_schedule import bands_equivalent, compute_iog_bands
from app.services.octopus_client import octopus_client
from app.services.safety_settings_service import safety_settings_service

logger = logging.getLogger(__name__)

_AUTO_SCHEDULE_KEY = "auto_schedule"


class AutoScheduleService:
    def __init__(self) -> None:
        self._last_run_at: datetime | None = None
        self._last_run_message: str = ""
        self._last_write_audit_id: int | None = None
        self._computed_bands: list[TouBandWrite] = []
        self._next_cheap_windows: list[DispatchWindow] = []
        self._last_mode_fix_at: datetime | None = None

    _MODE_FIX_COOLDOWN = timedelta(minutes=30)

    async def _load_config(self, db: AsyncSession) -> dict[str, Any]:
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _AUTO_SCHEDULE_KEY))
        if row:
            try:
                return json.loads(row.value)
            except json.JSONDecodeError:
                pass
        return {
            "enabled": settings.auto_schedule_enabled,
            "soc_floor_pct": settings.auto_schedule_soc_floor_pct,
        }

    async def _save_config(self, db: AsyncSession, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload)
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _AUTO_SCHEDULE_KEY))
        if row:
            row.value = encoded
        else:
            db.add(AppSettingRow(key=_AUTO_SCHEDULE_KEY, value=encoded))
        await db.commit()

    async def get_status(self, db: AsyncSession) -> AutoScheduleStatus:
        config = await self._load_config(db)
        return AutoScheduleStatus(
            enabled=bool(config.get("enabled", False)),
            soc_floor_pct=int(config.get("soc_floor_pct", settings.auto_schedule_soc_floor_pct)),
            last_run_at=self._last_run_at,
            last_run_message=self._last_run_message,
            last_write_audit_id=self._last_write_audit_id,
            next_cheap_windows=self._next_cheap_windows,
            computed_bands=self._computed_bands,
        )

    async def set_config(
        self,
        db: AsyncSession,
        request: AutoScheduleConfigRequest,
    ) -> AutoScheduleStatus:
        current = await self._load_config(db)
        payload = {
            "enabled": request.enabled,
            "soc_floor_pct": request.soc_floor_pct
            if request.soc_floor_pct is not None
            else int(current.get("soc_floor_pct", settings.auto_schedule_soc_floor_pct)),
        }
        await self._save_config(db, payload)
        return await self.get_status(db)

    async def compute_bands(self, db: AsyncSession) -> list[TouBandWrite]:
        config = await self._load_config(db)
        soc_floor = int(config.get("soc_floor_pct", settings.auto_schedule_soc_floor_pct))
        overnight_target = int(
            config.get("overnight_target_pct", settings.auto_schedule_overnight_target_pct)
        )
        dispatches = await octopus_client.get_dispatches()
        self._next_cheap_windows = list(dispatches.planned)
        bands = compute_iog_bands(
            offpeak_start=dispatches.off_peak_window.start,
            offpeak_end=dispatches.off_peak_window.end,
            planned=dispatches.planned,
            soc_floor_pct=soc_floor,
            overnight_target_pct=overnight_target,
        )
        self._computed_bands = bands
        return bands

    async def _ensure_self_use_on_peak(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
        settings_payload: InverterSettingsResponse,
        config: dict[str, Any],
    ) -> str | None:
        """Switch out of sell mode during peak when the battery should discharge.

        Sunsynk inverters often revert to "Selling first" overnight; on peak rate
        with high SOC that prevents using stored energy for the house load.
        """
        if self._last_mode_fix_at is not None:
            if datetime.now(timezone.utc) - self._last_mode_fix_at < self._MODE_FIX_COOLDOWN:
                return None

        from app.schemas.domain import SystemWorkMode

        if work_mode_from_sunsynk(settings_payload.sys_work_mode) != SystemWorkMode.SELLING:
            return None

        soc_floor = int(config.get("soc_floor_pct", settings.auto_schedule_soc_floor_pct))
        try:
            metrics = await adapter.get_live_metrics()
        except Exception:  # noqa: BLE001
            return None

        if metrics.battery_soc_pct <= soc_floor + 5:
            return None

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
            logger.warning("Auto schedule: failed to load Octopus dispatches", exc_info=True)

        window = evaluate_charge_window(
            grid_import_w=metrics.grid_import_w,
            battery_soc_pct=metrics.battery_soc_pct,
            battery_power_w=metrics.battery_power_w,
            active_band=settings_payload.active_band,
            offpeak_start=offpeak_start,
            offpeak_end=offpeak_end,
            planned=planned,
            now=metrics.timestamp,
        )
        if window.cheap_now:
            return None

        result = await control_service.set_operating_mode(
            db,
            adapter,
            username="auto-scheduler",
            role=UserRole.ADMIN,
            request=OperatingModeRequest(mode=InverterMode.SELF_USE),
        )
        if not result.success:
            logger.warning("Auto-align mode fix failed: %s", result.message)
            return None
        self._last_mode_fix_at = datetime.now(timezone.utc)
        audit = result.audit_id
        logger.info("Auto-align switched inverter to self-use on peak (audit #%s)", audit)
        return f"Switched to self-use (audit #{audit})"

    async def run_once(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
    ) -> AutoScheduleStatus:
        self._last_run_at = datetime.now(timezone.utc)
        config = await self._load_config(db)
        if not config.get("enabled", False):
            self._last_run_message = "Auto-align disabled"
            logger.info("Auto-align skipped: disabled in config")
            return await self.get_status(db)

        if ev_load_detector.car_charging_likely:
            self._last_run_message = "EV charging likely — skipping auto-align"
            logger.info("Auto-align skipped: EV charging likely")
            return await self.get_status(db)

        if (
            settings.is_production
            or safety_settings_service.effective_read_only()
            or not safety_settings_service.effective_enable_live_writes()
        ):
            self._last_run_message = (
                "Writes disabled (production display-only, read-only, or live writes off)"
            )
            # This is the most common reason a correct schedule is never applied,
            # so log it at WARNING rather than letting it fail silently.
            logger.warning(
                "Auto-align computed a schedule but did not write it: live writes are "
                "disabled (production=%s, read_only=%s, enable_live_writes=%s).",
                settings.is_production,
                safety_settings_service.effective_read_only(),
                safety_settings_service.effective_enable_live_writes(),
            )
            return await self.get_status(db)

        settings_payload = await adapter.get_inverter_settings()
        if settings_payload is None or not settings_payload.write_allowed:
            self._last_run_message = "Inverter settings unavailable or write not allowed"
            logger.warning(
                "Auto-align could not write: inverter settings unavailable or account "
                "lacks write permission."
            )
            return await self.get_status(db)

        desired = await self.compute_bands(db)
        current = [
            TouBandWrite(
                slot=band.slot,
                start=band.start,
                target_soc_pct=band.target_soc_pct,
                grid_charge_enabled=band.grid_charge_enabled,
                power_w=band.power_w,
            )
            for band in settings_payload.bands
        ]
        if bands_equivalent(desired, current):
            self._last_run_message = "Schedule already aligned — no write needed"
            logger.info("Auto-align: schedule already aligned, no write needed")
        else:
            logger.info(
                "Auto-align writing TOU bands: %s",
                ", ".join(
                    f"slot{b.slot}@{b.start} cap{b.target_soc_pct} "
                    f"grid{'On' if b.grid_charge_enabled else 'Off'}"
                    for b in desired
                ),
            )
            result = await control_service.set_tou_bands(
                db,
                adapter,
                username="auto-scheduler",
                role=UserRole.ADMIN,
                request=TouBandsRequest(bands=desired),
            )
            if result.success:
                self._last_write_audit_id = result.audit_id
                self._last_run_message = f"Schedule updated (audit #{result.audit_id})"
                logger.info(
                    "Auto-align wrote schedule (audit #%s, verified=%s)",
                    result.audit_id,
                    getattr(result, "verified", None),
                )
            else:
                self._last_run_message = result.message
                logger.error("Auto-align write failed: %s", result.message)

        mode_note = await self._ensure_self_use_on_peak(db, adapter, settings_payload, config)
        if mode_note:
            if self._last_run_message:
                self._last_run_message = f"{self._last_run_message}; {mode_note}"
            else:
                self._last_run_message = mode_note

        return await self.get_status(db)


auto_schedule_service = AutoScheduleService()
