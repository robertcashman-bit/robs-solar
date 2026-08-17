from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import settings
from app.schemas.domain import HealthResponse
from app.services.lunchflow_settings_service import lunchflow_settings_service
from app.services.quickfile_settings_service import quickfile_settings_service
from app.services.safety_settings_service import safety_settings_service
from app.services.truelayer_settings_service import truelayer_settings_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Finance health probe — no solar adapter call on the critical path.

    ``adapter_mode`` and ``read_only`` are leftover solar/control settings. They
    do not mean bank balances are simulated. Finance live status is
    ``data_source=finance`` plus the QuickFile / Lunch Flow / TrueLayer flags.
    """
    quickfile = quickfile_settings_service.env_configured()
    lunchflow = lunchflow_settings_service.env_configured()
    truelayer = truelayer_settings_service.env_configured()
    read_only = safety_settings_service.effective_read_only()
    return HealthResponse(
        status="ok",
        adapter_mode=settings.adapter_mode,
        data_source="finance",
        read_only=read_only,
        timestamp=datetime.now(timezone.utc),
        plant_id=None,
        quickfile_env_configured=quickfile,
        lunchflow_env_configured=lunchflow,
        truelayer_env_configured=truelayer,
        finance_bank_reads_ready=bool(quickfile or lunchflow or truelayer),
        solar_control_writes_gated=read_only,
    )
