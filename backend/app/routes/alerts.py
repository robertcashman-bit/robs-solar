from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin_csrf, require_viewer
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.services.alert_service import alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return {"alerts": await alert_service.list_alerts(db)}


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    request: Request,
    _: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ = request
    result = await alert_service.acknowledge(db, alert_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return result
