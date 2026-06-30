"""Unit tests for Sunsynk TOU parsing helpers."""

from datetime import datetime

from app.adapters.sunsynk_tou import (
    active_band_index,
    diagnose_battery_hold,
    parse_tou_bands,
    permissions_allow_write,
)
from app.schemas.domain import TouBand


def test_parse_tou_bands_from_settings_payload() -> None:
    data = {
        "sellTime1": "00:00",
        "sellTime2": "06:20",
        "sellTime3": "11:00",
        "cap1": "100",
        "cap2": "19",
        "cap3": "20",
        "time1on": "true",
        "time2on": "true",
        "time3on": "false",
    }
    bands = parse_tou_bands(data)
    assert len(bands) == 3
    assert bands[1].target_soc_pct == 19
    assert bands[1].grid_charge_enabled is True
    assert bands[2].grid_charge_enabled is False


def test_active_band_index_at_mid_morning() -> None:
    bands = [
        TouBand(slot=1, start="00:00", end="06:20", grid_charge_enabled=True),
        TouBand(slot=2, start="06:20", end="11:00", grid_charge_enabled=True),
        TouBand(slot=3, start="11:00", end="24:00", grid_charge_enabled=False),
    ]
    now = datetime(2026, 6, 29, 9, 30)
    assert active_band_index(bands, now) == 2


def test_diagnose_grid_charge_hold() -> None:
    bands = [
        TouBand(
            slot=2,
            start="06:20",
            end="11:00",
            target_soc_pct=19,
            grid_charge_enabled=True,
        )
    ]
    msg = diagnose_battery_hold(bands, 2)
    assert "grid charge is ON" in msg


def test_permissions_allow_write_view_only() -> None:
    assert permissions_allow_write(["smart.rule.view", "smart.light.view"]) is False
