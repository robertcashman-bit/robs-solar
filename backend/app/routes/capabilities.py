from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_adapter
from app.auth.dependencies import require_viewer
from app.auth.sessions import SessionData
from app.config import settings
from app.db.session import get_db
from app.schemas.domain import SystemCapabilitiesResponse
from app.services.octopus_client import octopus_client
from app.services.safety_settings_service import safety_settings_service

router = APIRouter(tags=["capabilities"])


@router.get("/capabilities", response_model=SystemCapabilitiesResponse)
async def get_capabilities(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> SystemCapabilitiesResponse:
    adapter = get_adapter()
    caps = await adapter.get_capabilities()
    safety = await safety_settings_service.get_settings(db)
    data_source = "simulated" if settings.adapter_mode.lower() == "simulator" else "live"
    return SystemCapabilitiesResponse(
        adapter=caps,
        data_source=data_source,
        read_only=safety.read_only,
        enable_live_writes=safety.enable_live_writes,
        sunsynk_enable_unverified_writes=settings.sunsynk_enable_unverified_writes,
        plant_id=settings.sunsynk_plant_id or None,
        plant_name=None,
        modbus_host=settings.modbus_host or None,
        modbus_port=settings.modbus_port,
        modbus_slave_id=settings.modbus_slave_id,
        poll_interval_live_seconds=settings.poll_interval_live_seconds,
        poll_interval_energy_seconds=settings.poll_interval_energy_seconds,
        octopus_configured=octopus_client.configured(),
    )
