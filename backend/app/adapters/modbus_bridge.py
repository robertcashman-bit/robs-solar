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


class ModbusBridgeAdapter(InverterAdapter):
    """HTTP client for a local Modbus bridge service.

    The browser and FastAPI never access RS485 directly.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.modbus_bridge_url.rstrip("/") if settings.modbus_bridge_url else None,
            headers={"Authorization": f"Bearer {settings.modbus_bridge_token}"}
            if settings.modbus_bridge_token
            else {},
            timeout=10.0,
        )

    async def get_capabilities(self) -> AdapterCapabilities:
        configured = bool(settings.modbus_bridge_url)
        return AdapterCapabilities(
            mode="modbus_bridge",
            supports_read=configured,
            supports_write=False,
            supported_writes=[],
            notes=[
                "Modbus register mappings are not verified in v1.",
                "Configure MODBUS_BRIDGE_URL to a local HTTP bridge service.",
            ],
        )

    async def get_live_metrics(self) -> LiveMetrics:
        from datetime import datetime, timezone

        if not settings.modbus_bridge_url:
            raise AdapterError("MODBUS_BRIDGE_URL not configured")
        response = await self._client.get("/metrics/live")
        response.raise_for_status()
        data = response.json()
        return LiveMetrics(
            pv_power_w=float(data["pv_power_w"]),
            battery_soc_pct=float(data["battery_soc_pct"]),
            house_load_w=float(data["house_load_w"]),
            grid_import_w=float(data["grid_import_w"]),
            grid_export_w=float(data["grid_export_w"]),
            inverter_mode=InverterMode(data.get("inverter_mode", "self_use")),
            inverter_status=InverterStatus(data.get("inverter_status", "online")),
            daily_pv_kwh=float(data.get("daily_pv_kwh", 0)),
            daily_import_kwh=float(data.get("daily_import_kwh", 0)),
            daily_export_kwh=float(data.get("daily_export_kwh", 0)),
            timestamp=datetime.now(timezone.utc),
        )

    async def get_connectivity(self) -> ConnectivityStatus:
        from datetime import datetime, timezone

        if not settings.modbus_bridge_url:
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode="modbus_bridge",
                adapter_connected=False,
                degraded_reason="MODBUS_BRIDGE_URL not configured",
            )
        try:
            response = await self._client.get("/health")
            response.raise_for_status()
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode="modbus_bridge",
                adapter_connected=True,
                last_successful_poll=datetime.now(timezone.utc),
            )
        except httpx.HTTPError as exc:
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode="modbus_bridge",
                adapter_connected=False,
                degraded_reason=str(exc),
            )

    async def set_export_limit(self, request: ExportLimitRequest) -> dict[str, Any]:
        raise UnsupportedWriteError("Modbus bridge export limit write not yet verified.")

    async def set_schedule(self, request: ScheduleRequest) -> dict[str, Any]:
        raise UnsupportedWriteError("Modbus bridge schedule write not yet verified.")

    async def set_operating_mode(self, request: OperatingModeRequest) -> dict[str, Any]:
        raise UnsupportedWriteError("Modbus bridge operating mode write not yet verified.")

    async def get_last_known_good(self) -> Optional[dict[str, Any]]:
        return None
