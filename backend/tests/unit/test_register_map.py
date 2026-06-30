"""Unit tests for Sunsynk register decoding."""

from app.adapters import register_map as reg


def test_decode_scaled_register() -> None:
    assert reg.decode_register(2305, reg.REG_GRID_VOLTAGE) == 230.5


def test_decode_signed_grid_export() -> None:
    assert reg.decode_register(1500, reg.REG_GRID_POWER) == 1500.0
    imp, exp = reg.split_grid_power(1500.0)
    assert imp == 0.0
    assert exp == 1500.0


def test_tou_slot_address() -> None:
    assert reg.tou_slot_address(0, 0) == 250
    assert reg.tou_slot_address(1, 2) == 257


def test_encode_time_hhmm() -> None:
    assert reg.encode_time_hhmm("23:30") == 2330


def test_decode_signed_grid_import() -> None:
    raw = 64036  # -1500 W as uint16
    assert reg.decode_register(raw, reg.REG_GRID_POWER) == -1500.0
    imp, exp = reg.split_grid_power(-1500.0)
    assert imp == 1500.0
    assert exp == 0.0
