from app.adapters.base import InverterAdapter
from app.adapters.home_assistant import HomeAssistantAdapter
from app.adapters.modbus_bridge import ModbusBridgeAdapter
from app.adapters.modbus_tcp import ModbusTcpAdapter
from app.adapters.simulator import SimulatorAdapter
from app.config import settings


def get_adapter() -> InverterAdapter:
    mode = settings.adapter_mode.lower()
    if mode in {"sunsynk_connect", "sunsynk"}:
        # Sunsynk was removed from the product. Keep the process running on the
        # simulator so leftover ADAPTER_MODE values cannot lock the live account.
        return SimulatorAdapter()
    if mode == "simulator":
        return SimulatorAdapter()
    if mode == "home_assistant":
        return HomeAssistantAdapter()
    if mode == "modbus_bridge":
        return ModbusBridgeAdapter()
    if mode == "modbus_tcp":
        return ModbusTcpAdapter()
    raise ValueError(f"Unknown adapter mode: {settings.adapter_mode}")


def get_sunsynk_adapter() -> None:
    """Sunsynk was removed; leftover lockout routes treat this as inactive."""
    return None
