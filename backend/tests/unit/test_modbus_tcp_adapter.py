"""Unit tests for Modbus TCP adapter (mocked client)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.modbus_tcp import ModbusTcpAdapter
from app.schemas.domain import (
    BatteryControlRequest,
    ExportLimitRequest,
    ForceBatteryAction,
    ForceBatteryRequest,
    ScheduleAction,
    ScheduleRequest,
    ScheduleWindow,
)


@pytest.fixture
def adapter() -> ModbusTcpAdapter:
    return ModbusTcpAdapter()


@pytest.mark.asyncio
async def test_set_export_limit_clamps_and_writes(adapter: ModbusTcpAdapter, monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.read_only", False)
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.enable_live_writes", True)
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.modbus_host", "192.168.1.10")

    write = AsyncMock(return_value=MagicMock(isError=lambda: False))
    client = MagicMock()
    client.connected = True
    client.connect = AsyncMock(return_value=True)
    client.write_register = write
    client.close = MagicMock()

    with patch.object(adapter, "_get_client", AsyncMock(return_value=client)):
        result = await adapter.set_export_limit(ExportLimitRequest(limit_w=8000))
    assert result["export_limit_w"] == 8000
    assert write.await_count >= 2


@pytest.mark.asyncio
async def test_set_schedule_writes_six_slots(adapter: ModbusTcpAdapter, monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.read_only", False)
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.enable_live_writes", True)
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.modbus_host", "192.168.1.10")

    write = AsyncMock(return_value=MagicMock(isError=lambda: False))
    client = MagicMock()
    client.connected = True
    client.connect = AsyncMock(return_value=True)
    client.write_register = write

    request = ScheduleRequest(
        windows=[
            ScheduleWindow(start="23:30", end="05:30", action=ScheduleAction.CHARGE, power_w=3000),
        ]
    )
    with patch.object(adapter, "_get_client", AsyncMock(return_value=client)):
        result = await adapter.set_schedule(request)
    assert len(result["windows"]) == 1
    assert write.await_count >= 6


@pytest.mark.asyncio
async def test_battery_control_clamps(adapter: ModbusTcpAdapter, monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.read_only", False)
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.enable_live_writes", True)
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.modbus_host", "192.168.1.10")

    write = AsyncMock(return_value=MagicMock(isError=lambda: False))
    client = MagicMock()
    client.connected = True
    client.connect = AsyncMock(return_value=True)
    client.write_register = write

    with patch.object(adapter, "_get_client", AsyncMock(return_value=client)):
        applied = await adapter.set_battery_control(
            BatteryControlRequest.model_construct(
                charge_current_a=250,
                grid_charge_current_a=80,
            )
        )
    assert applied["charge_current_a"] == 190
    assert applied["grid_charge_current_a"] == 50


@pytest.mark.asyncio
async def test_force_battery_charge(adapter: ModbusTcpAdapter, monkeypatch) -> None:
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.read_only", False)
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.enable_live_writes", True)
    monkeypatch.setattr("app.adapters.modbus_tcp.settings.modbus_host", "192.168.1.10")

    write = AsyncMock(return_value=MagicMock(isError=lambda: False))
    client = MagicMock()
    client.connected = True
    client.connect = AsyncMock(return_value=True)
    client.write_register = write

    with patch.object(adapter, "_get_client", AsyncMock(return_value=client)):
        result = await adapter.force_battery(ForceBatteryRequest(action=ForceBatteryAction.CHARGE))
    assert result["action"] == "charge"
    assert result["charge_current_a"] == 190
