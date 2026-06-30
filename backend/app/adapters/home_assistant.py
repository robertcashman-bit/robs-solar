from typing import Any, Optional

import httpx

from app.adapters.base import InverterAdapter
from app.config import settings
from app.schemas.domain import (
    AdapterCapabilities,
    AdapterError,
    ConnectivityStatus,
    ExportLimitRequest,
    InverterMode,
    InverterStatus,
    LiveMetrics,
    OperatingModeRequest,
    ScheduleRequest,
    UnsupportedWriteError,
)


class HomeAssistantAdapter(InverterAdapter):
    """Home Assistant REST adapter.

    Reads use configurable entity IDs. Writes require verified service mappings.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.ha_base_url.rstrip("/") if settings.ha_base_url else None,
            headers={"Authorization": f"Bearer {settings.ha_token}"} if settings.ha_token else {},
            timeout=10.0,
        )

    async def get_capabilities(self) -> AdapterCapabilities:
        read_ready = bool(settings.ha_base_url and settings.ha_entity_pv_power)
        write_ready = bool(settings.ha_service_export_limit)
        supported_writes: list[str] = []
        notes = [
            "Configure HA entity IDs via environment variables.",
            "Write support requires verified HA service mappings.",
        ]
        if write_ready:
            supported_writes.append("export_limit")
        return AdapterCapabilities(
            mode="home_assistant",
            supports_read=read_ready,
            supports_write=write_ready,
            supported_writes=supported_writes,
            notes=notes,
        )

    async def _fetch_state(self, entity_id: str) -> float:
        if not settings.ha_base_url or not entity_id:
            raise AdapterError("Home Assistant entity not configured")
        response = await self._client.get(f"/api/states/{entity_id}")
        response.raise_for_status()
        state = response.json().get("state")
        try:
            return float(state)
        except (TypeError, ValueError) as exc:
            raise AdapterError(f"Invalid HA state for {entity_id}") from exc

    async def get_live_metrics(self) -> LiveMetrics:
        from datetime import datetime, timezone

        if not settings.ha_base_url:
            raise AdapterError("HA_BASE_URL not configured")
        return LiveMetrics(
            pv_power_w=await self._fetch_state(settings.ha_entity_pv_power),
            battery_soc_pct=await self._fetch_state(settings.ha_entity_battery_soc),
            house_load_w=await self._fetch_state(settings.ha_entity_house_load),
            grid_import_w=await self._fetch_state(settings.ha_entity_grid_import),
            grid_export_w=await self._fetch_state(settings.ha_entity_grid_export),
            inverter_mode=InverterMode.SELF_USE,
            inverter_status=InverterStatus.ONLINE,
            daily_pv_kwh=0.0,
            daily_import_kwh=0.0,
            daily_export_kwh=0.0,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_connectivity(self) -> ConnectivityStatus:
        from datetime import datetime, timezone

        if not settings.ha_base_url:
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode="home_assistant",
                adapter_connected=False,
                degraded_reason="HA_BASE_URL not configured",
            )
        try:
            response = await self._client.get("/api/")
            response.raise_for_status()
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode="home_assistant",
                adapter_connected=True,
                last_successful_poll=datetime.now(timezone.utc),
            )
        except httpx.HTTPError as exc:
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode="home_assistant",
                adapter_connected=False,
                degraded_reason=str(exc),
            )

    async def set_export_limit(self, request: ExportLimitRequest) -> dict[str, Any]:
        if not settings.ha_service_export_limit:
            raise UnsupportedWriteError(
                "HA export limit service not configured. Set HA_SERVICE_EXPORT_LIMIT."
            )
        # TODO: verified HA service call once entity/service mapping confirmed by user.
        raise UnsupportedWriteError("Home Assistant export limit write not yet verified.")

    async def set_schedule(self, request: ScheduleRequest) -> dict[str, Any]:
        raise UnsupportedWriteError("Home Assistant schedule write not yet verified.")

    async def set_operating_mode(self, request: OperatingModeRequest) -> dict[str, Any]:
        raise UnsupportedWriteError("Home Assistant operating mode write not yet verified.")

    async def get_last_known_good(self) -> Optional[dict[str, Any]]:
        return None
