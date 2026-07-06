"""Direct Modbus TCP adapter for Sunsynk inverters via RS485-WiFi dongle."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymodbus.client import AsyncModbusTcpClient

from app.adapters import register_map as reg
from app.adapters.base import InverterAdapter
from app.config import settings
from app.schemas.domain import (
    AdapterCapabilities,
    AdapterError,
    BatteryControlRequest,
    ConnectivityStatus,
    ExportLimitRequest,
    ForceBatteryRequest,
    InverterStatus,
    LiveMetrics,
    OperatingModeRequest,
    ScheduleRequest,
    SystemWorkMode,
    UnsupportedWriteError,
    work_mode_to_inverter_mode,
)

logger = logging.getLogger(__name__)
_MODE = "modbus_tcp"
_WRITE_DELAY_S = 0.5


class ModbusTcpAdapter(InverterAdapter):
    def __init__(self) -> None:
        self._client: Optional[AsyncModbusTcpClient] = None
        self._offline = False

    def _ensure_configured(self) -> None:
        if not settings.modbus_host:
            raise AdapterError("MODBUS_HOST not configured")

    async def _get_client(self) -> AsyncModbusTcpClient:
        self._ensure_configured()
        if self._client is None or not self._client.connected:
            self._client = AsyncModbusTcpClient(
                settings.modbus_host,
                port=settings.modbus_port,
            )
            connected = await self._client.connect()
            if not connected:
                self._offline = True
                raise AdapterError("Modbus TCP connection failed")
            self._offline = False
        return self._client

    async def _read_register(self, register: reg.RegisterDef) -> int:
        attempts = max(1, settings.modbus_max_retries + 1)
        last_exc: Optional[Exception] = None
        for _ in range(attempts):
            try:
                client = await self._get_client()
                result = await client.read_holding_registers(
                    register.address,
                    count=register.count,
                    slave=settings.modbus_slave_id,
                )
                if result.isError():
                    raise AdapterError(f"Modbus read error at {register.address}")
                return int(result.registers[0])
            except (AdapterError, OSError, asyncio.TimeoutError) as exc:
                last_exc = exc
                self._offline = True
                if self._client:
                    self._client.close()
                    self._client = None
                await asyncio.sleep(0.2)
        raise AdapterError(f"Modbus read failed after {attempts} attempts: {last_exc}")

    async def _read_scaled(self, register: reg.RegisterDef) -> float:
        raw = await self._read_register(register)
        return reg.decode_register(raw, register)

    async def get_capabilities(self) -> AdapterCapabilities:
        configured = bool(settings.modbus_host)
        write_ready = bool(configured and settings.enable_live_writes and not settings.read_only)
        return AdapterCapabilities(
            mode=_MODE,
            supports_read=configured,
            supports_write=write_ready,
            supported_writes=[
                "export_limit",
                "operating_mode",
                "schedule",
                "battery",
                "force_battery",
            ]
            if write_ready
            else [],
            notes=[
                "Direct Modbus TCP to Sunsynk inverter (community register map, UNVERIFIED).",
                "Configure MODBUS_HOST to your RS485-WiFi dongle IP.",
            ],
        )

    async def get_live_metrics(self) -> LiveMetrics:
        grid_w = await self._read_scaled(reg.REG_GRID_POWER)
        grid_import, grid_export = reg.split_grid_power(grid_w)
        pv1 = await self._read_scaled(reg.REG_PV1_POWER)
        pv2 = await self._read_scaled(reg.REG_PV2_POWER)
        batt_power = await self._read_scaled(reg.REG_BATTERY_POWER)
        soc = await self._read_scaled(reg.REG_BATTERY_SOC)
        if soc <= 0:
            soc = await self._read_scaled(reg.REG_BATTERY_SOC_ALT)

        work_raw = int(await self._read_register(reg.REG_SYSTEM_WORK_MODE))
        work_mode = SystemWorkMode.BATTERY_FIRST
        if work_raw == 0:
            work_mode = SystemWorkMode.SELLING
        elif work_raw == 1:
            work_mode = SystemWorkMode.BYPASS

        return LiveMetrics(
            pv_power_w=max(0.0, pv1 + pv2),
            pv1_power_w=max(0.0, pv1),
            pv2_power_w=max(0.0, pv2),
            battery_soc_pct=min(100.0, max(0.0, soc)),
            battery_power_w=batt_power,
            battery_voltage_v=await self._read_scaled(reg.REG_BATTERY_VOLTAGE),
            battery_current_a=await self._read_scaled(reg.REG_BATTERY_CURRENT),
            battery_temp_c=await self._read_scaled(reg.REG_BATTERY_TEMP),
            battery_soh_pct=min(100.0, max(0.0, await self._read_scaled(reg.REG_BATTERY_SOH))),
            house_load_w=max(0.0, await self._read_scaled(reg.REG_LOAD_POWER)),
            grid_import_w=grid_import,
            grid_export_w=grid_export,
            grid_voltage_v=await self._read_scaled(reg.REG_GRID_VOLTAGE),
            grid_frequency_hz=await self._read_scaled(reg.REG_GRID_FREQUENCY),
            inverter_mode=work_mode_to_inverter_mode(work_mode),
            inverter_status=InverterStatus.OFFLINE if self._offline else InverterStatus.ONLINE,
            daily_pv_kwh=max(0.0, await self._read_scaled(reg.REG_DAILY_PV)),
            daily_import_kwh=max(0.0, await self._read_scaled(reg.REG_DAILY_GRID_IMPORT)),
            daily_export_kwh=max(0.0, await self._read_scaled(reg.REG_DAILY_GRID_EXPORT)),
            daily_battery_charge_kwh=max(
                0.0, await self._read_scaled(reg.REG_DAILY_BATTERY_CHARGE)
            ),
            daily_battery_discharge_kwh=max(
                0.0, await self._read_scaled(reg.REG_DAILY_BATTERY_DISCHARGE)
            ),
            system_work_mode=work_mode,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_connectivity(self) -> ConnectivityStatus:
        if not settings.modbus_host:
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode=_MODE,
                adapter_connected=False,
                degraded_reason="MODBUS_HOST not configured",
            )
        try:
            await self._read_register(reg.REG_BATTERY_SOC)
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode=_MODE,
                adapter_connected=True,
                last_successful_poll=datetime.now(timezone.utc),
            )
        except AdapterError as exc:
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode=_MODE,
                adapter_connected=False,
                degraded_reason=str(exc),
            )

    def _ensure_writes_enabled(self) -> None:
        if settings.read_only:
            raise UnsupportedWriteError("Read-only mode is enabled.")
        if not settings.enable_live_writes:
            raise UnsupportedWriteError("Live writes disabled. Set ENABLE_LIVE_WRITES=true.")

    async def _write_register(self, address: int, value: int) -> None:
        self._ensure_writes_enabled()
        client = await self._get_client()
        result = await client.write_register(address, value, slave=settings.modbus_slave_id)
        if result.isError():
            raise AdapterError(f"Modbus write failed at {address}")
        await asyncio.sleep(_WRITE_DELAY_S)

    async def set_export_limit(self, request: ExportLimitRequest) -> dict[str, Any]:
        limit = min(request.limit_w, reg.MAX_EXPORT_LIMIT_W)
        await self._write_register(reg.REG_EXPORT_LIMIT_POWER.address, limit)
        await self._write_register(reg.REG_EXPORT_LIMIT_ENABLE.address, 1)
        return {"export_limit_w": limit, "verified": False}

    async def set_operating_mode(self, request: OperatingModeRequest) -> dict[str, Any]:
        from app.schemas.domain import inverter_mode_to_work_mode

        work = inverter_mode_to_work_mode(request.mode)
        raw = {"selling": 0, "bypass": 1, "battery_first": 2}[work.value]
        await self._write_register(reg.REG_SYSTEM_WORK_MODE.address, raw)
        return {"operating_mode": request.mode.value, "verified": False}

    async def set_schedule(self, request: ScheduleRequest) -> dict[str, Any]:
        windows = request.windows[: reg.REG_TOU_SLOT_COUNT]
        for slot in range(reg.REG_TOU_SLOT_COUNT):
            enabled_addr = reg.tou_slot_address(slot, 4)
            if slot < len(windows):
                window = windows[slot]
                action = reg.SCHEDULE_ACTION_CODES.get(window.action.value, 0)
                await self._write_register(
                    reg.tou_slot_address(slot, 0),
                    reg.encode_time_hhmm(window.start),
                )
                await self._write_register(
                    reg.tou_slot_address(slot, 1),
                    reg.encode_time_hhmm(window.end),
                )
                await self._write_register(reg.tou_slot_address(slot, 2), action)
                await self._write_register(
                    reg.tou_slot_address(slot, 3),
                    min(window.power_w or 0, reg.MAX_EXPORT_LIMIT_W),
                )
                await self._write_register(enabled_addr, 1)
            else:
                await self._write_register(enabled_addr, 0)
        return {"windows": [w.model_dump() for w in windows]}

    async def set_battery_control(self, request: BatteryControlRequest) -> dict[str, Any]:
        applied: dict[str, int] = {}
        if request.charge_current_a is not None:
            value = min(request.charge_current_a, reg.MAX_BATTERY_CHARGE_A)
            await self._write_register(reg.REG_BATTERY_CHARGE_CURRENT.address, value)
            applied["charge_current_a"] = value
        if request.discharge_current_a is not None:
            value = min(request.discharge_current_a, reg.MAX_BATTERY_DISCHARGE_A)
            await self._write_register(reg.REG_BATTERY_DISCHARGE_CURRENT.address, value)
            applied["discharge_current_a"] = value
        if request.grid_charge_current_a is not None:
            value = min(request.grid_charge_current_a, reg.MAX_GRID_CHARGE_A)
            await self._write_register(reg.REG_GRID_CHARGE_POWER.address, value)
            applied["grid_charge_current_a"] = value
        return applied

    async def force_battery(self, request: ForceBatteryRequest) -> dict[str, Any]:
        if request.action.value == "charge":
            amps = reg.MAX_BATTERY_CHARGE_A
            await self._write_register(reg.REG_BATTERY_CHARGE_CURRENT.address, amps)
            await self._write_register(reg.REG_BATTERY_DISCHARGE_CURRENT.address, 0)
            return {"action": "charge", "charge_current_a": amps}
        if request.action.value == "discharge":
            amps = reg.MAX_BATTERY_DISCHARGE_A
            await self._write_register(reg.REG_BATTERY_DISCHARGE_CURRENT.address, amps)
            await self._write_register(reg.REG_BATTERY_CHARGE_CURRENT.address, 0)
            return {"action": "discharge", "discharge_current_a": amps}
        await self._write_register(reg.REG_BATTERY_CHARGE_CURRENT.address, 0)
        await self._write_register(reg.REG_BATTERY_DISCHARGE_CURRENT.address, 0)
        return {"action": "stop"}

    async def get_last_known_good(self) -> Optional[dict[str, Any]]:
        return None
