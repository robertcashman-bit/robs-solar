from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, validate_csrf
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.domain import NotificationSettings, NotificationSettingsStatus
from app.services.notification_settings_service import notification_settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/notifications", response_model=NotificationSettingsStatus)
async def get_notification_settings(
    _: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsStatus:
    return await notification_settings_service.get_status(db)


@router.put("/notifications", response_model=NotificationSettingsStatus)
async def update_notification_settings(
    request: Request,
    body: NotificationSettings,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsStatus:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    return await notification_settings_service.set_settings(db, body)
