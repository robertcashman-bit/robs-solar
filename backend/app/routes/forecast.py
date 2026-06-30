from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import require_viewer
from app.auth.sessions import SessionData
from app.services.forecast_service import forecast_service

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("")
async def solar_forecast(_: SessionData = Depends(require_viewer)) -> dict:
    try:
        return await forecast_service.get_forecast()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Forecast unavailable: {exc}",
        ) from exc
