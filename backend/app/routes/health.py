from datetime import datetime, timezone

from fastapi import APIRouter

from app.adapters.factory import get_adapter
from app.config import settings
from app.schemas.domain import HealthResponse
from app.services.safety_settings_service import safety_settings_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    adapter = get_adapter()
    _ = await adapter.get_capabilities()
    return HealthResponse(
        status="ok",
        adapter_mode=settings.adapter_mode,
        read_only=safety_settings_service.effective_read_only(),
        timestamp=datetime.now(timezone.utc),
    )
