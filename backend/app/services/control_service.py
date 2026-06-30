import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import InverterAdapter
from app.config import settings
from app.db.models import ConfigSnapshotRow
from app.schemas.domain import (
    AdapterError,
    AuditOutcome,
    BatteryControlRequest,
    ControlWriteResult,
    ExportLimitRequest,
    ForceBatteryRequest,
    OperatingModeRequest,
    RestoreResult,
    ScheduleRequest,
    TouBandsRequest,
    UnsupportedWriteError,
    UserRole,
)
from app.services.audit_service import audit_service


class ControlService:
    async def _save_snapshot(
        self,
        db: AsyncSession,
        *,
        username: str,
        snapshot_type: str,
        payload: dict,
    ) -> ConfigSnapshotRow:
        row = ConfigSnapshotRow(
            timestamp=datetime.now(timezone.utc),
            username=username,
            snapshot_type=snapshot_type,
            payload=json.dumps(payload),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    async def _with_verification(
        self,
        adapter: InverterAdapter,
        result: ControlWriteResult,
        *,
        verify_kind: str,
        request_payload: Optional[dict] = None,
    ) -> ControlWriteResult:
        if not result.success:
            return result
        if settings.adapter_mode.lower() == "simulator":
            result.verified = True
            result.verification_message = "Confirmed (simulator)"
            return result
        await asyncio.sleep(3)
        try:
            if verify_kind == "tou" and request_payload:
                desired = request_payload.get("bands", [])
                settings_payload = await adapter.get_inverter_settings()
                if settings_payload is None:
                    result.verification_pending = True
                    result.verification_message = "Could not read back inverter settings"
                    return result
                current = [
                    {
                        "start": b.start,
                        "target_soc_pct": b.target_soc_pct,
                        "grid_charge_enabled": b.grid_charge_enabled,
                    }
                    for b in settings_payload.bands
                ]
                wanted = [
                    {
                        "start": b["start"],
                        "target_soc_pct": b.get("target_soc_pct"),
                        "grid_charge_enabled": b.get("grid_charge_enabled"),
                    }
                    for b in desired
                ]
                if current[: len(wanted)] == wanted:
                    result.verified = True
                    result.verification_message = "Schedule confirmed on inverter"
                else:
                    result.verification_pending = True
                    result.verification_message = (
                        "Write sent — inverter has not reported matching values yet"
                    )
            elif verify_kind == "export_limit" and request_payload is not None:
                limit_w = request_payload.get("limit_w")
                settings_payload = await adapter.get_inverter_settings()
                if settings_payload and limit_w is not None:
                    result.verified = True
                    result.verification_message = "Export limit write acknowledged"
                else:
                    result.verification_pending = True
                    result.verification_message = "Export limit pending confirmation"
            elif verify_kind == "operating_mode" and request_payload is not None:
                mode = request_payload.get("mode")
                settings_payload = await adapter.get_inverter_settings()
                if settings_payload and mode:
                    result.verified = True
                    result.verification_message = "Operating mode write acknowledged"
                else:
                    result.verification_pending = True
                    result.verification_message = "Mode change pending confirmation"
            else:
                result.verification_pending = True
                result.verification_message = "Write sent — awaiting inverter confirmation"
        except Exception as exc:
            result.verification_pending = True
            result.verification_message = f"Read-back failed: {exc}"
        return result

    async def set_export_limit(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
        *,
        username: str,
        role: UserRole,
        request: ExportLimitRequest,
    ) -> ControlWriteResult:
        try:
            applied = await adapter.set_export_limit(request)
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="set_export_limit",
                request_payload=request.model_dump(),
                validation_result="valid",
                adapter_response=json.dumps(applied),
                outcome=AuditOutcome.SUCCESS,
            )
            await self._save_snapshot(
                db,
                username=username,
                snapshot_type="export_limit",
                payload=applied,
            )
            result = ControlWriteResult(
                success=True,
                message="Export limit updated",
                audit_id=audit_row.id,
                applied_value=applied,
            )
            return await self._with_verification(
                adapter, result, verify_kind="export_limit", request_payload=request.model_dump()
            )
        except UnsupportedWriteError as exc:
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="set_export_limit",
                request_payload=request.model_dump(),
                validation_result="valid",
                adapter_response=str(exc),
                outcome=AuditOutcome.FAILED,
            )
            return ControlWriteResult(
                success=False,
                message=str(exc),
                audit_id=audit_row.id,
            )
        except AdapterError as exc:
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="set_export_limit",
                request_payload=request.model_dump(),
                validation_result="valid",
                adapter_response=str(exc),
                outcome=AuditOutcome.FAILED,
            )
            return ControlWriteResult(
                success=False,
                message=str(exc),
                audit_id=audit_row.id,
            )

    async def set_schedule(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
        *,
        username: str,
        role: UserRole,
        request: ScheduleRequest,
    ) -> ControlWriteResult:
        try:
            applied = await adapter.set_schedule(request)
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="set_schedule",
                request_payload=request.model_dump(),
                validation_result="valid",
                adapter_response=json.dumps(applied),
                outcome=AuditOutcome.SUCCESS,
            )
            await self._save_snapshot(
                db,
                username=username,
                snapshot_type="schedule",
                payload=applied,
            )
            return ControlWriteResult(
                success=True,
                message="Schedule updated",
                audit_id=audit_row.id,
                applied_value=applied,
            )
        except (UnsupportedWriteError, AdapterError) as exc:
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="set_schedule",
                request_payload=request.model_dump(),
                validation_result="valid",
                adapter_response=str(exc),
                outcome=AuditOutcome.FAILED,
            )
            return ControlWriteResult(
                success=False,
                message=str(exc),
                audit_id=audit_row.id,
            )

    async def set_tou_bands(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
        *,
        username: str,
        role: UserRole,
        request: TouBandsRequest,
    ) -> ControlWriteResult:
        try:
            applied = await adapter.set_tou_bands(request)
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="set_tou_bands",
                request_payload=request.model_dump(),
                validation_result="valid",
                adapter_response=json.dumps(applied),
                outcome=AuditOutcome.SUCCESS,
            )
            await self._save_snapshot(
                db,
                username=username,
                snapshot_type="tou_bands",
                payload=applied,
            )
            result = ControlWriteResult(
                success=True,
                message="Time-of-use schedule updated",
                audit_id=audit_row.id,
                applied_value=applied,
            )
            return await self._with_verification(
                adapter,
                result,
                verify_kind="tou",
                request_payload=request.model_dump(),
            )
        except (UnsupportedWriteError, AdapterError) as exc:
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="set_tou_bands",
                request_payload=request.model_dump(),
                validation_result="valid",
                adapter_response=str(exc),
                outcome=AuditOutcome.FAILED,
            )
            return ControlWriteResult(
                success=False,
                message=str(exc),
                audit_id=audit_row.id,
            )

    async def set_operating_mode(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
        *,
        username: str,
        role: UserRole,
        request: OperatingModeRequest,
    ) -> ControlWriteResult:
        try:
            applied = await adapter.set_operating_mode(request)
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="set_operating_mode",
                request_payload=request.model_dump(),
                validation_result="valid",
                adapter_response=json.dumps(applied),
                outcome=AuditOutcome.SUCCESS,
            )
            await self._save_snapshot(
                db,
                username=username,
                snapshot_type="operating_mode",
                payload=applied,
            )
            result = ControlWriteResult(
                success=True,
                message="Operating mode updated",
                audit_id=audit_row.id,
                applied_value=applied,
            )
            return await self._with_verification(
                adapter,
                result,
                verify_kind="operating_mode",
                request_payload=request.model_dump(),
            )
        except (UnsupportedWriteError, AdapterError) as exc:
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="set_operating_mode",
                request_payload=request.model_dump(),
                validation_result="valid",
                adapter_response=str(exc),
                outcome=AuditOutcome.FAILED,
            )
            return ControlWriteResult(
                success=False,
                message=str(exc),
                audit_id=audit_row.id,
            )

    async def set_battery_control(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
        *,
        username: str,
        role: UserRole,
        request: BatteryControlRequest,
    ) -> ControlWriteResult:
        try:
            applied = await adapter.set_battery_control(request)
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="set_battery_control",
                request_payload=request.model_dump(exclude_none=True),
                validation_result="valid",
                adapter_response=json.dumps(applied),
                outcome=AuditOutcome.SUCCESS,
            )
            await self._save_snapshot(
                db,
                username=username,
                snapshot_type="battery",
                payload=applied,
            )
            return ControlWriteResult(
                success=True,
                message="Battery settings updated",
                audit_id=audit_row.id,
                applied_value=applied,
            )
        except (UnsupportedWriteError, AdapterError) as exc:
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="set_battery_control",
                request_payload=request.model_dump(exclude_none=True),
                validation_result="valid",
                adapter_response=str(exc),
                outcome=AuditOutcome.FAILED,
            )
            return ControlWriteResult(
                success=False,
                message=str(exc),
                audit_id=audit_row.id,
            )

    async def force_battery(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
        *,
        username: str,
        role: UserRole,
        request: ForceBatteryRequest,
    ) -> ControlWriteResult:
        try:
            applied = await adapter.force_battery(request)
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="force_battery",
                request_payload=request.model_dump(),
                validation_result="valid",
                adapter_response=json.dumps(applied),
                outcome=AuditOutcome.SUCCESS,
            )
            return ControlWriteResult(
                success=True,
                message=f"Force {request.action.value} applied",
                audit_id=audit_row.id,
                applied_value=applied,
            )
        except (UnsupportedWriteError, AdapterError) as exc:
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="force_battery",
                request_payload=request.model_dump(),
                validation_result="valid",
                adapter_response=str(exc),
                outcome=AuditOutcome.FAILED,
            )
            return ControlWriteResult(
                success=False,
                message=str(exc),
                audit_id=audit_row.id,
            )

    async def restore_last_known_good(
        self,
        db: AsyncSession,
        adapter: InverterAdapter,
        *,
        username: str,
        role: UserRole,
    ) -> RestoreResult:
        snapshot = await adapter.get_last_known_good()
        if not snapshot:
            audit_row = await audit_service.record(
                db,
                username=username,
                role=role,
                action="restore_last_known_good",
                request_payload={},
                validation_result="valid",
                adapter_response="No snapshot available",
                outcome=AuditOutcome.FAILED,
            )
            return RestoreResult(
                success=False,
                message="No last known good configuration available",
                audit_id=audit_row.id,
            )

        if "export_limit_w" in snapshot:
            await adapter.set_export_limit(
                ExportLimitRequest(limit_w=int(snapshot["export_limit_w"]))
            )
        if "operating_mode" in snapshot:
            from app.schemas.domain import InverterMode

            await adapter.set_operating_mode(
                OperatingModeRequest(mode=InverterMode(snapshot["operating_mode"]))
            )

        row = await self._save_snapshot(
            db,
            username=username,
            snapshot_type="restore",
            payload=snapshot,
        )
        audit_row = await audit_service.record(
            db,
            username=username,
            role=role,
            action="restore_last_known_good",
            request_payload={},
            validation_result="valid",
            adapter_response=json.dumps(snapshot),
            outcome=AuditOutcome.SUCCESS,
        )
        return RestoreResult(
            success=True,
            message="Restored last known good configuration",
            audit_id=audit_row.id,
            restored_snapshot_id=row.id,
        )


control_service = ControlService()
