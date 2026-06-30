from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, validate_csrf
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.domain import AuditOutcome, SafetySettings, SafetySettingsUpdate
from app.services.audit_service import audit_service
from app.services.safety_settings_service import safety_settings_service

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/safety", response_model=SafetySettings)
async def get_safety_settings(
    _: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SafetySettings:
    return await safety_settings_service.get_settings(db)


@router.put("/safety", response_model=SafetySettings)
async def update_safety_settings(
    request: Request,
    body: SafetySettingsUpdate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SafetySettings:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    result = await safety_settings_service.update_settings(db, body)
    await audit_service.record(
        db,
        username=session.username,
        role=session.role,
        action="update_safety_settings",
        request_payload=body.model_dump(exclude_none=True),
        validation_result="valid",
        adapter_response=None,
        outcome=AuditOutcome.SUCCESS,
    )
    return result
