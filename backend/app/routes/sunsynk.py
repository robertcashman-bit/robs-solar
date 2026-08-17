from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_sunsynk_adapter
from app.auth.dependencies import require_admin, require_viewer, validate_csrf
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.domain import (
    AdapterError,
    AuditOutcome,
    SunsynkAuthStatus,
    SunsynkVerificationCodeRequest,
)
from app.services.audit_service import audit_service

router = APIRouter(prefix="/integrations/sunsynk", tags=["sunsynk"])


@router.get("/auth-status", response_model=SunsynkAuthStatus)
async def sunsynk_auth_status(_: SessionData = Depends(require_viewer)) -> SunsynkAuthStatus:
    adapter = get_sunsynk_adapter()
    if adapter is None:
        return SunsynkAuthStatus(verification_required=False, message=None)
    status_payload = adapter.auth_status()
    return SunsynkAuthStatus(
        verification_required=bool(status_payload.get("verification_required")),
        message=status_payload.get("message"),
    )


@router.post("/verification-code", response_model=SunsynkAuthStatus)
async def submit_sunsynk_verification_code(
    request: Request,
    body: SunsynkVerificationCodeRequest,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SunsynkAuthStatus:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    adapter = get_sunsynk_adapter()
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sunsynk adapter is not active",
        )
    try:
        result = await adapter.submit_verification_code(body.code)
    except AdapterError as exc:
        await audit_service.record(
            db,
            username=session.username,
            role=session.role,
            action="sunsynk_verification_code",
            request_payload={"code_length": len(body.code.strip())},
            validation_result="adapter_error",
            adapter_response=str(exc),
            outcome=AuditOutcome.FAILED,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    await audit_service.record(
        db,
        username=session.username,
        role=session.role,
        action="sunsynk_verification_code",
        request_payload={"code_length": len(body.code.strip())},
        validation_result="valid",
        adapter_response="authenticated",
        outcome=AuditOutcome.SUCCESS,
    )
    return SunsynkAuthStatus(
        verification_required=bool(result.get("verification_required")),
        message=result.get("message"),
    )
