from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_adapter
from app.auth.dependencies import require_admin, require_viewer, validate_csrf
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.domain import (
    AuditOutcome,
    AutomationRule,
    AutomationRulesResponse,
    AutoScheduleConfigRequest,
    AutoScheduleStatus,
    BatteryControlRequest,
    ControlWriteResult,
    ExportLimitRequest,
    ForceBatteryRequest,
    InverterSettingsResponse,
    OperatingModeRequest,
    PeakImportGuardConfigRequest,
    PeakImportGuardStatus,
    ScheduleRequest,
    TouBandsRequest,
)
from app.services.audit_service import audit_service
from app.services.auto_schedule_service import auto_schedule_service
from app.services.control_service import control_service
from app.services.peak_import_guard_service import peak_import_guard_service
from app.services.rules_engine import rules_engine
from app.services.safety_settings_service import safety_settings_service

router = APIRouter(prefix="/controls", tags=["controls"])


@router.get("/settings", response_model=InverterSettingsResponse)
async def get_inverter_settings(
    _: SessionData = Depends(require_viewer),
) -> InverterSettingsResponse:
    adapter = get_adapter()
    settings_payload = await adapter.get_inverter_settings()
    if settings_payload is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inverter settings are not available for this adapter",
        )
    return settings_payload


async def _ensure_writes_allowed(
    request: Request,
    session: SessionData,
    db: AsyncSession,
    *,
    action: str,
    payload: dict,
) -> None:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    safety = await safety_settings_service.get_settings(db)
    if safety.read_only:
        await audit_service.record(
            db,
            username=session.username,
            role=session.role,
            action=action,
            request_payload=payload,
            validation_result="blocked_read_only",
            adapter_response="READ_ONLY mode enabled",
            outcome=AuditOutcome.REJECTED,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System is in read-only mode",
        )


@router.post("/export-limit", response_model=ControlWriteResult)
async def set_export_limit(
    body: ExportLimitRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ControlWriteResult:
    await _ensure_writes_allowed(
        request, session, db, action="set_export_limit", payload=body.model_dump()
    )
    adapter = get_adapter()
    result = await control_service.set_export_limit(
        db, adapter, username=session.username, role=session.role, request=body
    )
    if not result.success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.message)
    return result


@router.post("/schedule", response_model=ControlWriteResult)
async def set_schedule(
    body: ScheduleRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ControlWriteResult:
    await _ensure_writes_allowed(
        request, session, db, action="set_schedule", payload=body.model_dump()
    )
    adapter = get_adapter()
    result = await control_service.set_schedule(
        db, adapter, username=session.username, role=session.role, request=body
    )
    if not result.success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.message)
    return result


@router.post("/tou", response_model=ControlWriteResult)
async def set_tou_bands(
    body: TouBandsRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ControlWriteResult:
    await _ensure_writes_allowed(
        request, session, db, action="set_tou_bands", payload=body.model_dump()
    )
    adapter = get_adapter()
    result = await control_service.set_tou_bands(
        db, adapter, username=session.username, role=session.role, request=body
    )
    if not result.success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.message)
    return result


@router.post("/operating-mode", response_model=ControlWriteResult)
async def set_operating_mode(
    body: OperatingModeRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ControlWriteResult:
    await _ensure_writes_allowed(
        request, session, db, action="set_operating_mode", payload=body.model_dump()
    )
    adapter = get_adapter()
    result = await control_service.set_operating_mode(
        db, adapter, username=session.username, role=session.role, request=body
    )
    if not result.success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.message)
    return result


@router.post("/battery", response_model=ControlWriteResult)
async def set_battery_control(
    body: BatteryControlRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ControlWriteResult:
    await _ensure_writes_allowed(
        request,
        session,
        db,
        action="set_battery_control",
        payload=body.model_dump(exclude_none=True),
    )
    adapter = get_adapter()
    result = await control_service.set_battery_control(
        db, adapter, username=session.username, role=session.role, request=body
    )
    if not result.success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.message)
    return result


@router.post("/force-battery", response_model=ControlWriteResult)
async def force_battery(
    body: ForceBatteryRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ControlWriteResult:
    await _ensure_writes_allowed(
        request, session, db, action="force_battery", payload=body.model_dump()
    )
    adapter = get_adapter()
    result = await control_service.force_battery(
        db, adapter, username=session.username, role=session.role, request=body
    )
    if not result.success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.message)
    return result


@router.get("/auto-schedule", response_model=AutoScheduleStatus)
async def get_auto_schedule_status(
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AutoScheduleStatus:
    _ = session
    return await auto_schedule_service.get_status(db)


@router.post("/auto-schedule", response_model=AutoScheduleStatus)
async def set_auto_schedule(
    body: AutoScheduleConfigRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AutoScheduleStatus:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    await auto_schedule_service.set_config(db, body)
    await audit_service.record(
        db,
        username=session.username,
        role=session.role,
        action="set_auto_schedule",
        request_payload=body.model_dump(),
        validation_result="valid",
        adapter_response=None,
        outcome=AuditOutcome.SUCCESS,
    )
    if body.enabled is True:
        adapter = get_adapter()
        return await auto_schedule_service.run_once(db, adapter)
    return await auto_schedule_service.get_status(db)


@router.get("/peak-import-guard", response_model=PeakImportGuardStatus)
async def get_peak_import_guard_status(
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PeakImportGuardStatus:
    _ = session
    return await peak_import_guard_service.get_status(db)


@router.post("/peak-import-guard", response_model=PeakImportGuardStatus)
async def set_peak_import_guard(
    body: PeakImportGuardConfigRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PeakImportGuardStatus:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    status = await peak_import_guard_service.set_config(db, body)
    await audit_service.record(
        db,
        username=session.username,
        role=session.role,
        action="set_peak_import_guard",
        request_payload=body.model_dump(),
        validation_result="valid",
        adapter_response=None,
        outcome=AuditOutcome.SUCCESS,
    )
    return status


@router.get("/rules", response_model=AutomationRulesResponse)
async def list_rules(
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AutomationRulesResponse:
    _ = session
    return await rules_engine.list_rules(db)


@router.post("/rules", response_model=AutomationRulesResponse)
async def add_rule(
    body: AutomationRule,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AutomationRulesResponse:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    return await rules_engine.add_rule(db, body)


@router.delete("/rules/{rule_id}", response_model=AutomationRulesResponse)
async def delete_rule(
    rule_id: str,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AutomationRulesResponse:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    return await rules_engine.delete_rule(db, rule_id)
