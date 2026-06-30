"""Auto-align Sunsynk TOU bands to IOG cheap windows."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import InverterAdapter
from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.domain import (
    AutoScheduleConfigRequest,
    AutoScheduleStatus,
    DispatchWindow,
    TouBandsRequest,
    TouBandWrite,
    UserRole,
)
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

    async def _load_config(self, db: AsyncSession) -> dict[str, Any]:
        row = await db.scalar(
            select(AppSettingRow).where(AppSettingRow.key == _AUTO_SCHEDULE_KEY)
        )
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
        row = await db.scalar(
            select(AppSettingRow).where(AppSettingRow.key == _AUTO_SCHEDULE_KEY)
        )
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
        dispatches = await octopus_client.get_dispatches()
        self._next_cheap_windows = list(dispatches.planned)
        bands = compute_iog_bands(
            offpeak_start=dispatches.off_peak_window.start,
            offpeak_end=dispatches.off_peak_window.end,
            planned=dispatches.planned,
            soc_floor_pct=soc_floor,
        )
        self._computed_bands = bands
        return bands

    async def run_once(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
    ) -> AutoScheduleStatus:
        self._last_run_at = datetime.now(timezone.utc)
        config = await self._load_config(db)
        if not config.get("enabled", False):
            self._last_run_message = "Auto-align disabled"
            return await self.get_status(db)

        if ev_load_detector.car_charging_likely:
            self._last_run_message = "EV charging likely — skipping auto-align"
            return await self.get_status(db)

        if (
            safety_settings_service.effective_read_only()
            or not safety_settings_service.effective_enable_live_writes()
        ):
            self._last_run_message = "Writes disabled (read-only or live writes off)"
            return await self.get_status(db)

        settings_payload = await adapter.get_inverter_settings()
        if settings_payload is None or not settings_payload.write_allowed:
            self._last_run_message = "Inverter settings unavailable or write not allowed"
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
            return await self.get_status(db)

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
        else:
            self._last_run_message = result.message
        return await self.get_status(db)


auto_schedule_service = AutoScheduleService()
