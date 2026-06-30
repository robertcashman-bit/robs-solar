import pytest

from app.adapters.simulator import SimulatorAdapter
from app.schemas.domain import (
    ExportLimitRequest,
    InverterMode,
    OperatingModeRequest,
    TouBandsRequest,
    TouBandWrite,
)


@pytest.mark.asyncio
async def test_simulator_returns_metrics() -> None:
    adapter = SimulatorAdapter(seed=1)
    metrics = await adapter.get_live_metrics()
    assert metrics.pv_power_w >= 0
    assert 0 <= metrics.battery_soc_pct <= 100


@pytest.mark.asyncio
async def test_simulator_supports_export_limit_write() -> None:
    adapter = SimulatorAdapter(seed=1)
    result = await adapter.set_export_limit(ExportLimitRequest(limit_w=2500))
    assert result["export_limit_w"] == 2500


@pytest.mark.asyncio
async def test_simulator_operating_mode_write() -> None:
    adapter = SimulatorAdapter(seed=1)
    result = await adapter.set_operating_mode(OperatingModeRequest(mode=InverterMode.BACKUP))
    assert result["operating_mode"] == "backup"


@pytest.mark.asyncio
async def test_simulator_settings_are_writable_with_six_bands() -> None:
    adapter = SimulatorAdapter(seed=1)
    settings = await adapter.get_inverter_settings()
    assert settings.write_allowed is True
    assert len(settings.bands) == 6
    assert settings.active_band is not None


@pytest.mark.asyncio
async def test_simulator_set_tou_bands_round_trips() -> None:
    adapter = SimulatorAdapter(seed=1)
    result = await adapter.set_tou_bands(
        TouBandsRequest(
            bands=[
                TouBandWrite(
                    slot=2,
                    start="05:30",
                    target_soc_pct=55,
                    grid_charge_enabled=True,
                    power_w=4000,
                )
            ]
        )
    )
    assert result["bands"] == 1
    settings = await adapter.get_inverter_settings()
    band2 = next(b for b in settings.bands if b.slot == 2)
    assert band2.start == "05:30"
    assert band2.target_soc_pct == 55
    assert band2.grid_charge_enabled is True
