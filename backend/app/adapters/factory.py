from app.adapters.base import InverterAdapter
from app.adapters.home_assistant import HomeAssistantAdapter
from app.adapters.modbus_bridge import ModbusBridgeAdapter
from app.adapters.modbus_tcp import ModbusTcpAdapter
from app.adapters.simulator import SimulatorAdapter
from app.adapters.sunsynk_connect import SunsynkConnectAdapter
from app.config import settings


def get_adapter() -> InverterAdapter:
    mode = settings.adapter_mode.lower()
    if mode == "simulator":
        return SimulatorAdapter()
    if mode == "sunsynk_connect":
        return SunsynkConnectAdapter()
    if mode == "home_assistant":
        return HomeAssistantAdapter()
    if mode == "modbus_bridge":
        return ModbusBridgeAdapter()
    if mode == "modbus_tcp":
        return ModbusTcpAdapter()
    raise ValueError(f"Unknown adapter mode: {settings.adapter_mode}")
