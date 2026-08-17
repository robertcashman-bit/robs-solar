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
        supported_writes: list[str] = []
        notes = [
            "Configure HA entity IDs via environment variables.",
            "Write support uses verified HA service mappings from env.",
        ]
        if settings.ha_service_export_limit:
            supported_writes.append("export_limit")
        if settings.ha_service_schedule:
            supported_writes.append("schedule")
        if settings.ha_service_operating_mode:
            supported_writes.append("operating_mode")
        write_ready = bool(supported_writes)
        return AdapterCapabilities(
            mode="home_assistant",
            supports_read=read_ready,
            supports_write=write_ready,
            supported_writes=supported_writes,
            notes=notes,
        )

    async def _call_service(self, service_id: str, service_data: dict[str, Any]) -> dict[str, Any]:
        if not settings.ha_base_url:
            raise AdapterError("HA_BASE_URL not configured")
        if "." not in service_id:
            raise AdapterError(f"Invalid HA service id: {service_id}")
        domain, service = service_id.split(".", 1)
        response = await self._client.post(
            f"/api/services/{domain}/{service}",
            json=service_data,
        )
        response.raise_for_status()
        return {"service": service_id, "service_data": service_data, "status": "ok"}

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
        service_data: dict[str, Any] = {"limit_w": request.limit_w}
        if settings.ha_entity_export_limit:
            service_data["entity_id"] = settings.ha_entity_export_limit
        return await self._call_service(settings.ha_service_export_limit, service_data)

    async def set_schedule(self, request: ScheduleRequest) -> dict[str, Any]:
        if not settings.ha_service_schedule:
            raise UnsupportedWriteError(
                "HA schedule service not configured. Set HA_SERVICE_SCHEDULE."
            )
        return await self._call_service(
            settings.ha_service_schedule,
            {"windows": [window.model_dump() for window in request.windows]},
        )

    async def set_operating_mode(self, request: OperatingModeRequest) -> dict[str, Any]:
        if not settings.ha_service_operating_mode:
            raise UnsupportedWriteError(
                "HA operating mode service not configured. Set HA_SERVICE_OPERATING_MODE."
            )
        service_data: dict[str, Any] = {"mode": request.mode.value}
        if settings.ha_entity_inverter_mode:
            service_data["entity_id"] = settings.ha_entity_inverter_mode
        return await self._call_service(settings.ha_service_operating_mode, service_data)

    async def get_last_known_good(self) -> Optional[dict[str, Any]]:
        return None
