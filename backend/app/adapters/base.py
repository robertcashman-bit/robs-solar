from abc import ABC, abstractmethod
from typing import Any, Optional

from app.schemas.domain import (
    AdapterCapabilities,
    BatteryControlRequest,
    ConnectivityStatus,
    ExportLimitRequest,
    ForceBatteryRequest,
    LiveMetrics,
    OperatingModeRequest,
    ScheduleRequest,
    TouBandsRequest,
    UnsupportedWriteError,
)


class InverterAdapter(ABC):
    @abstractmethod
    async def get_capabilities(self) -> AdapterCapabilities:
        raise NotImplementedError

    @abstractmethod
    async def get_live_metrics(self) -> LiveMetrics:
        raise NotImplementedError

    @abstractmethod
    async def get_connectivity(self) -> ConnectivityStatus:
        raise NotImplementedError

    @abstractmethod
    async def set_export_limit(self, request: ExportLimitRequest) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def set_schedule(self, request: ScheduleRequest) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def set_operating_mode(self, request: OperatingModeRequest) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_last_known_good(self) -> Optional[dict[str, Any]]:
        raise NotImplementedError

    async def set_tou_bands(self, request: TouBandsRequest) -> dict[str, Any]:
        raise UnsupportedWriteError("TOU band editing not supported by this adapter.")

    async def set_battery_control(self, request: BatteryControlRequest) -> dict[str, Any]:
        raise UnsupportedWriteError("Battery control not supported by this adapter.")

    async def force_battery(self, request: ForceBatteryRequest) -> dict[str, Any]:
        raise UnsupportedWriteError("Force battery action not supported by this adapter.")

    async def get_inverter_settings(self) -> Any:
        """Optional: live inverter TOU/settings. None when unsupported."""
        return None
