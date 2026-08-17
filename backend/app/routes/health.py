from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import settings
from app.schemas.domain import HealthResponse
from app.services.lunchflow_settings_service import lunchflow_settings_service
from app.services.quickfile_settings_service import quickfile_settings_service
from app.services.safety_settings_service import safety_settings_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Finance health probe — no solar adapter call on the critical path."""
    return HealthResponse(
        status="ok",
        adapter_mode=settings.adapter_mode,
        data_source="finance",
        read_only=safety_settings_service.effective_read_only(),
        timestamp=datetime.now(timezone.utc),
        plant_id=None,
        quickfile_env_configured=quickfile_settings_service.env_configured(),
        lunchflow_env_configured=lunchflow_settings_service.env_configured(),
    )
