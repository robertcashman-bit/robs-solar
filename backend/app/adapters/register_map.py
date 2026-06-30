"""Sunsynk 8.8kW ECCO Modbus register map (community-inferred, UNVERIFIED)."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RegisterDef:
    address: int
    scale: float = 1.0
    signed: bool = False
    count: int = 1


# Read-only monitoring
REG_GRID_FREQUENCY = RegisterDef(72, scale=0.01)
REG_GRID_VOLTAGE = RegisterDef(73, scale=0.1)
REG_GRID_POWER = RegisterDef(79, signed=True)
REG_BATTERY_VOLTAGE = RegisterDef(169, scale=0.01)
REG_BATTERY_CURRENT = RegisterDef(170, scale=0.01, signed=True)
REG_BATTERY_POWER = RegisterDef(171, signed=True)
REG_LOAD_POWER = RegisterDef(175)
REG_BATTERY_TEMP = RegisterDef(182, scale=1.0)
REG_BATTERY_SOC = RegisterDef(183)
REG_BATTERY_SOH = RegisterDef(184)
REG_PV1_VOLTAGE = RegisterDef(186, scale=0.1)
REG_PV1_CURRENT = RegisterDef(187, scale=0.1)
REG_PV1_POWER = RegisterDef(188)
REG_PV2_VOLTAGE = RegisterDef(189, scale=0.1)
REG_PV2_CURRENT = RegisterDef(190, scale=0.1)
REG_PV2_POWER = RegisterDef(191)
REG_DAILY_BATTERY_CHARGE = RegisterDef(200, scale=0.1)
REG_DAILY_BATTERY_DISCHARGE = RegisterDef(201, scale=0.1)
REG_SYSTEM_WORK_MODE = RegisterDef(232)
REG_GRID_CHARGE_POWER = RegisterDef(216)
REG_BATTERY_CHARGE_VOLTAGE = RegisterDef(213, scale=0.1)
REG_BATTERY_CHARGE_CURRENT = RegisterDef(219)
REG_BATTERY_DISCHARGE_CURRENT = RegisterDef(220)
REG_EXPORT_LIMIT_POWER = RegisterDef(243)
REG_EXPORT_LIMIT_ENABLE = RegisterDef(244)
REG_DAILY_GRID_IMPORT = RegisterDef(527, scale=0.1)
REG_DAILY_GRID_EXPORT = RegisterDef(528, scale=0.1)
REG_DAILY_PV = RegisterDef(529, scale=0.1)
REG_BATTERY_SOC_ALT = RegisterDef(588)

# TOU schedule slots start at 250 (6 slots, 5 registers each)
REG_TOU_SLOT_BASE = 250
REG_TOU_SLOT_COUNT = 6
REG_TOU_REGISTERS_PER_SLOT = 5

# Safety clamps
MAX_EXPORT_LIMIT_W = 8000
MAX_BATTERY_CHARGE_A = 190
MAX_BATTERY_DISCHARGE_A = 190
MAX_GRID_CHARGE_A = 50


def decode_register(raw: int, reg: RegisterDef) -> float:
    value = raw
    if reg.signed and value > 32767:
        value -= 65536
    return float(value) * reg.scale


def split_grid_power(watts: float) -> tuple[float, float]:
    """Register 79: positive=export, negative=import."""
    if watts >= 0:
        return 0.0, max(0.0, watts)
    return max(0.0, -watts), 0.0


def work_mode_from_register(value: int) -> Optional[int]:
    if value in (0, 1, 2):
        return value
    return None


def encode_time_hhmm(hhmm: str) -> int:
    hour_text, minute_text = hhmm.split(":")
    return int(hour_text) * 100 + int(minute_text)


SCHEDULE_ACTION_CODES = {"idle": 0, "charge": 1, "discharge": 2}


def tou_slot_address(slot_index: int, offset: int) -> int:
    if slot_index < 0 or slot_index >= REG_TOU_SLOT_COUNT:
        raise ValueError(f"TOU slot index must be 0-{REG_TOU_SLOT_COUNT - 1}")
    return REG_TOU_SLOT_BASE + slot_index * REG_TOU_REGISTERS_PER_SLOT + offset
