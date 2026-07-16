"""Automatic remediation when importing from grid at peak rate with high SOC."""

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
    DispatchWindow,
    InverterMode,
    LiveMetrics,
    OperatingModeRequest,
    PeakImportGuardConfigRequest,
    PeakImportGuardStatus,
    UserRole,
    work_mode_to_inverter_mode,
)
from app.services.auto_schedule_service import auto_schedule_service
from app.services.charge_window_service import evaluate_charge_window
from app.services.control_service import control_service
from app.services.ev_load_detector import ev_load_detector
from app.services.octopus_client import octopus_client
from app.services.safety_settings_service import safety_settings_service

logger = logging.getLogger(__name__)

_KEY = "peak_import_guard"
_DISCHARGE_THRESHOLD_W = 100.0
_SOC_HEADROOM_PCT = 5
_USERNAME = "peak-import-guard"


def should_remediate(
    *,
    cheap_now: bool,
    grid_import_w: float,
    battery_soc_pct: float,
    battery_power_w: float | None,
    soc_floor_pct: int,
    import_threshold_w: float,
) -> bool:
    """Return True when peak import at high SOC while battery is not discharging enough."""
    return (
        not cheap_now
        and grid_import_w >= import_threshold_w
        and battery_soc_pct > soc_floor_pct + _SOC_HEADROOM_PCT
        and (battery_power_w is None or battery_power_w < _DISCHARGE_THRESHOLD_W)
    )


class PeakImportGuardService:
    def __init__(self) -> None:
        self._consecutive_samples: int = 0
        self._last_action_at: datetime | None = None
        self._last_action_message: str = ""
        self._last_audit_ids: list[int] = []
        self._armed: bool = False

    async def _load_config(self, db: AsyncSession) -> dict[str, Any]:
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _KEY))
        if row:
            try:
                return json.loads(row.value)
            except json.JSONDecodeError:
                pass
        return {
            "enabled": settings.peak_import_guard_enabled,
        }

    async def _save_config(self, db: AsyncSession, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload)
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _KEY))
        if row:
            row.value = encoded
        else:
            db.add(AppSettingRow(key=_KEY, value=encoded))
        await db.commit()

    async def set_config(
        self,
        db: AsyncSession,
        request: PeakImportGuardConfigRequest,
    ) -> PeakImportGuardStatus:
        current = await self._load_config(db)
        payload = {**current, "enabled": request.enabled}
        await self._save_config(db, payload)
        return await self.get_status(db)

    def _cooldown_ok(self) -> bool:
        if self._last_action_at is None:
            return True
        elapsed = datetime.now(timezone.utc) - self._last_action_at
        return elapsed >= timedelta(minutes=settings.peak_import_guard_cooldown_minutes)

    def _cooldown_remaining_seconds(self) -> int:
        if self._last_action_at is None:
            return 0
        elapsed = datetime.now(timezone.utc) - self._last_action_at
        remaining = timedelta(minutes=settings.peak_import_guard_cooldown_minutes) - elapsed
        return max(0, int(remaining.total_seconds()))

    async def get_status(self, db: AsyncSession) -> PeakImportGuardStatus:
        config = await self._load_config(db)
        return PeakImportGuardStatus(
            enabled=bool(config.get("enabled", settings.peak_import_guard_enabled)),
            armed=self._armed,
            last_action_at=self._last_action_at,
            last_action_message=self._last_action_message,
            last_audit_ids=list(self._last_audit_ids),
            consecutive_samples=self._consecutive_samples,
            cooldown_remaining_seconds=self._cooldown_remaining_seconds(),
        )

    async def _resolve_charge_context(
        self,
        adapter: InverterAdapter,
    ) -> tuple[str, str, list[DispatchWindow], Any | None]:
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
            logger.warning("Peak import guard: failed to load Octopus dispatches", exc_info=True)

        active_band = None
        try:
            settings_payload = await adapter.get_inverter_settings()
            active_band = settings_payload.active_band if settings_payload else None
        except Exception:  # noqa: BLE001
            logger.warning("Peak import guard: failed to load inverter settings", exc_info=True)

        return offpeak_start, offpeak_end, planned, active_band

    async def evaluate(
        self,
        db: AsyncSession,
        metrics: LiveMetrics,
        adapter: InverterAdapter,
    ) -> None:
        config = await self._load_config(db)
        if not config.get("enabled", settings.peak_import_guard_enabled):
            self._consecutive_samples = 0
            self._armed = False
            return

        auto_config = await auto_schedule_service._load_config(db)
        soc_floor = int(auto_config.get("soc_floor_pct", settings.auto_schedule_soc_floor_pct))
        offpeak_start, offpeak_end, planned, active_band = await self._resolve_charge_context(
            adapter
        )

        window_status = evaluate_charge_window(
            grid_import_w=metrics.grid_import_w,
            battery_soc_pct=metrics.battery_soc_pct,
            battery_power_w=metrics.battery_power_w,
            active_band=active_band,
            offpeak_start=offpeak_start,
            offpeak_end=offpeak_end,
            planned=planned,
            now=metrics.timestamp,
        )

        import_threshold = settings.peak_import_guard_threshold_w
        condition = should_remediate(
            cheap_now=window_status.cheap_now,
            grid_import_w=metrics.grid_import_w,
            battery_soc_pct=metrics.battery_soc_pct,
            battery_power_w=metrics.battery_power_w,
            soc_floor_pct=soc_floor,
            import_threshold_w=import_threshold,
        )

        if condition:
            self._consecutive_samples += 1
        else:
            self._consecutive_samples = 0

        sustained = self._consecutive_samples >= settings.peak_import_guard_sustained_samples
        self._armed = condition and sustained and self._cooldown_ok()

        if not sustained:
            return

        if ev_load_detector.car_charging_likely:
            return

        if (
            settings.is_production
            or safety_settings_service.effective_read_only()
            or not safety_settings_service.effective_enable_live_writes()
        ):
            return

        if not self._cooldown_ok():
            return

        try:
            settings_payload = await adapter.get_inverter_settings()
        except Exception:  # noqa: BLE001
            return
        if settings_payload is None or not settings_payload.write_allowed:
            return

        await self._remediate(db, adapter, metrics, auto_config, settings_payload)

    @staticmethod
    def _current_mode(
        metrics: LiveMetrics,
        settings_payload: Any | None,
    ) -> InverterMode:
        """Resolve the real operating mode.

        Prefer the inverter settings document's sysWorkMode (authoritative) and
        fall back to the live-metrics mode. Older flow parsing hardcoded self-use,
        so relying on metrics alone could miss a "Selling first" inverter.
        """
        work_mode = getattr(settings_payload, "system_work_mode", None)
        if work_mode is not None:
            return work_mode_to_inverter_mode(work_mode)
        raw = getattr(settings_payload, "sys_work_mode", None)
        mapped = work_mode_from_sunsynk(raw) if raw not in (None, "") else None
        if mapped is not None:
            return work_mode_to_inverter_mode(mapped)
        return metrics.inverter_mode

    async def _remediate(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
        metrics: LiveMetrics,
        auto_config: dict[str, Any],
        settings_payload: Any | None = None,
    ) -> None:
        actions: list[str] = []
        audit_ids: list[int] = []

        if not auto_config.get("enabled", False):
            await auto_schedule_service.set_config(
                db,
                AutoScheduleConfigRequest(
                    enabled=True,
                    soc_floor_pct=int(
                        auto_config.get("soc_floor_pct", settings.auto_schedule_soc_floor_pct)
                    ),
                ),
            )
            actions.append("enabled auto-align")

        if self._current_mode(metrics, settings_payload) == InverterMode.FEED_IN:
            result = await control_service.set_operating_mode(
                db,
                adapter,
                username=_USERNAME,
                role=UserRole.ADMIN,
                request=OperatingModeRequest(mode=InverterMode.SELF_USE),
            )
            if result.audit_id is not None:
                audit_ids.append(result.audit_id)
            if result.success:
                actions.append("switched to self-use")
            else:
                logger.warning("Peak import guard: mode change failed: %s", result.message)

        align_status = await auto_schedule_service.run_once(db, adapter)
        if align_status.last_write_audit_id is not None:
            audit_ids.append(align_status.last_write_audit_id)
        if align_status.last_run_message:
            actions.append(align_status.last_run_message)

        self._last_action_at = datetime.now(timezone.utc)
        self._last_audit_ids = audit_ids
        self._consecutive_samples = 0
        self._armed = False

        if actions:
            self._last_action_message = "; ".join(actions)
            logger.info("Peak import guard remediated: %s", self._last_action_message)
        else:
            self._last_action_message = "No changes needed"


peak_import_guard_service = PeakImportGuardService()
