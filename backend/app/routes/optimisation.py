"""Optimisation mode settings."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_viewer, validate_csrf
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.domain import AuditOutcome, OptimisationModeSettings
from app.services.audit_service import audit_service
from app.services.optimisation_mode_service import optimisation_mode_service

router = APIRouter(prefix="/optimisation", tags=["optimisation"])


@router.get("/mode", response_model=OptimisationModeSettings)
async def get_optimisation_mode(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> OptimisationModeSettings:
    return await optimisation_mode_service.get_settings(db)


@router.put("/mode", response_model=OptimisationModeSettings)
async def set_optimisation_mode(
    request: Request,
    body: OptimisationModeSettings,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OptimisationModeSettings:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    result = await optimisation_mode_service.set_settings(db, body)
    await audit_service.record(
        db,
        username=session.username,
        role=session.role,
        action="update_optimisation_mode",
        request_payload=body.model_dump(),
        validation_result="valid",
        adapter_response=None,
        outcome=AuditOutcome.SUCCESS,
    )
    return result
