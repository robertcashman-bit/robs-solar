from typing import Optional

from app.adapters.base import InverterAdapter
from app.adapters.home_assistant import HomeAssistantAdapter
from app.adapters.modbus_bridge import ModbusBridgeAdapter
from app.adapters.modbus_tcp import ModbusTcpAdapter
from app.adapters.simulator import SimulatorAdapter
from app.adapters.sunsynk_connect import SunsynkConnectAdapter
from app.config import settings

# The Sunsynk adapter holds an auth token and Sunsynk issues only one active
# token per account. A fresh adapter per call meant every caller (live poll,
# sampler, alert evaluation, etc.) logged in independently and concurrently,
# invalidating each other's tokens and raising spurious "authentication failed"
# alerts. Caching one instance lets them share a single token.
_sunsynk_adapter: Optional[SunsynkConnectAdapter] = None


def get_adapter() -> InverterAdapter:
    mode = settings.adapter_mode.lower()
    if mode == "simulator":
        return SimulatorAdapter()
    if mode == "sunsynk_connect":
        global _sunsynk_adapter
        if _sunsynk_adapter is None:
            _sunsynk_adapter = SunsynkConnectAdapter()
        return _sunsynk_adapter
    if mode == "home_assistant":
        return HomeAssistantAdapter()
    if mode == "modbus_bridge":
        return ModbusBridgeAdapter()
    if mode == "modbus_tcp":
        return ModbusTcpAdapter()
    raise ValueError(f"Unknown adapter mode: {settings.adapter_mode}")
