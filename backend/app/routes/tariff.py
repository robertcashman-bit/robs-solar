from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_viewer, validate_csrf
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.domain import AuditOutcome, TariffSettings
from app.services.audit_service import audit_service
from app.services.tariff_service import tariff_service

router = APIRouter(prefix="/tariff", tags=["tariff"])


@router.get("", response_model=TariffSettings)
async def get_tariff(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> TariffSettings:
    return await tariff_service.get_tariff(db)


@router.put("", response_model=TariffSettings)
async def update_tariff(
    request: Request,
    body: TariffSettings,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TariffSettings:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    result = await tariff_service.set_tariff(db, body)
    await audit_service.record(
        db,
        username=session.username,
        role=session.role,
        action="update_tariff",
        request_payload=body.model_dump(),
        validation_result="valid",
        adapter_response=None,
        outcome=AuditOutcome.SUCCESS,
    )
    return result
