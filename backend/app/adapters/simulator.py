import math
from datetime import datetime, timezone
from typing import Any, Optional

from app.adapters.base import InverterAdapter
from app.adapters.sunsynk_tou import active_band_index
from app.schemas.domain import (
    AdapterCapabilities,
    BatteryControlRequest,
    ConnectivityStatus,
    ExportLimitRequest,
    ForceBatteryRequest,
    InverterMode,
    InverterSettingsResponse,
    InverterStatus,
    LiveMetrics,
    OperatingModeRequest,
    ScheduleRequest,
    TouBand,
    TouBandsRequest,
    inverter_mode_to_work_mode,
)


class SimulatorAdapter(InverterAdapter):
    """Deterministic-ish simulator for development and tests."""

    def __init__(self, seed: int = 42) -> None:
        self._seed = seed
        self._tick = 0
        self._export_limit_w = 3000
        self._operating_mode = InverterMode.SELF_USE
        self._schedule: list[dict[str, Any]] = []
        self._bands: list[TouBand] = [
            TouBand(
                slot=1,
                start="00:00",
                end="06:00",
                target_soc_pct=100,
                grid_charge_enabled=True,
                power_w=3000,
            ),
            TouBand(
                slot=2,
                start="06:00",
                end="11:00",
                target_soc_pct=40,
                grid_charge_enabled=False,
                power_w=8000,
            ),
            TouBand(
                slot=3,
                start="11:00",
                end="16:00",
                target_soc_pct=40,
                grid_charge_enabled=False,
                power_w=8000,
            ),
            TouBand(
                slot=4,
                start="16:00",
                end="19:00",
                target_soc_pct=80,
                grid_charge_enabled=False,
                power_w=8000,
            ),
            TouBand(
                slot=5,
                start="19:00",
                end="22:00",
                target_soc_pct=40,
                grid_charge_enabled=False,
                power_w=8000,
            ),
            TouBand(
                slot=6,
                start="22:00",
                end="24:00",
                target_soc_pct=40,
                grid_charge_enabled=False,
                power_w=8000,
            ),
        ]
        self._battery = {
            "charge_current_a": 50,
            "discharge_current_a": 50,
            "grid_charge_current_a": 20,
        }
        self._last_known_good = {
            "export_limit_w": self._export_limit_w,
            "operating_mode": self._operating_mode.value,
            "schedule": self._schedule,
            "battery": self._battery,
        }

    async def get_capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            mode="simulator",
            supports_read=True,
            supports_write=True,
            supported_writes=[
                "export_limit",
                "schedule",
                "tou",
                "operating_mode",
                "battery",
                "force_battery",
            ],
            notes=["Simulator mode — safe for development and tests."],
        )

    def _next_metrics(self) -> LiveMetrics:
        self._tick += 1
        phase = self._tick + self._seed
        pv = max(0.0, 4200 * max(0.0, math.sin(phase / 8.0)))
        load = 1800 + (phase % 7) * 120
        export = max(0.0, pv - load) if pv > load else 0.0
        import_w = max(0.0, load - pv) if load > pv else 0.0
        soc = min(100.0, max(20.0, 55 + 15 * math.sin(phase / 20.0)))
        battery_power_w = pv + import_w - load - export
        pv1 = pv * 0.73
        pv2 = pv * 0.27
        return LiveMetrics(
            pv_power_w=round(pv, 1),
            pv1_power_w=round(pv1, 1),
            pv2_power_w=round(pv2, 1),
            battery_soc_pct=round(soc, 1),
            battery_power_w=round(battery_power_w, 1),
            battery_voltage_v=round(51.2 + soc * 0.03, 2),
            battery_current_a=round(battery_power_w / 51.2, 2),
            battery_temp_c=round(22.0 + (phase % 5), 1),
            battery_soh_pct=98.0,
            house_load_w=round(load, 1),
            grid_import_w=round(import_w, 1),
            grid_export_w=round(export, 1),
            grid_voltage_v=230.5,
            grid_frequency_hz=50.0,
            inverter_mode=self._operating_mode,
            inverter_status=InverterStatus.ONLINE,
            daily_pv_kwh=round(12.4 + (phase % 10) * 0.1, 2),
            daily_import_kwh=round(3.1 + (phase % 5) * 0.05, 2),
            daily_export_kwh=round(5.8 + (phase % 6) * 0.07, 2),
            daily_battery_charge_kwh=round(4.2 + (phase % 3) * 0.1, 2),
            daily_battery_discharge_kwh=round(3.8 + (phase % 4) * 0.08, 2),
            system_work_mode=inverter_mode_to_work_mode(self._operating_mode),
            timestamp=datetime.now(timezone.utc),
        )

    async def get_live_metrics(self) -> LiveMetrics:
        return self._next_metrics()

    async def get_connectivity(self) -> ConnectivityStatus:
        return ConnectivityStatus(
            backend_healthy=True,
            adapter_mode="simulator",
            adapter_connected=True,
            last_successful_poll=datetime.now(timezone.utc),
        )

    async def set_export_limit(self, request: ExportLimitRequest) -> dict[str, Any]:
        self._export_limit_w = request.limit_w
        self._last_known_good["export_limit_w"] = request.limit_w
        return {"export_limit_w": request.limit_w}

    async def set_schedule(self, request: ScheduleRequest) -> dict[str, Any]:
        self._schedule = [window.model_dump() for window in request.windows]
        self._last_known_good["schedule"] = self._schedule
        return {"windows": self._schedule}

    def _normalize_band_ends(self, bands: list[TouBand]) -> list[TouBand]:
        """Recompute band end times from sorted start times (matches Sunsynk TOU model)."""
        ordered = sorted(bands, key=lambda b: b.slot)
        normalized: list[TouBand] = []
        for idx, band in enumerate(ordered):
            next_start = ordered[idx + 1].start if idx + 1 < len(ordered) else "24:00"
            normalized.append(
                TouBand(
                    slot=band.slot,
                    start=band.start,
                    end=next_start,
                    target_soc_pct=band.target_soc_pct,
                    grid_charge_enabled=band.grid_charge_enabled,
                    power_w=band.power_w,
                )
            )
        return normalized

    async def set_tou_bands(self, request: TouBandsRequest) -> dict[str, Any]:
        by_slot = {b.slot: b for b in self._bands}
        for band in request.bands:
            existing = by_slot.get(band.slot)
            by_slot[band.slot] = TouBand(
                slot=band.slot,
                start=band.start,
                end=existing.end if existing else "24:00",
                target_soc_pct=band.target_soc_pct,
                grid_charge_enabled=band.grid_charge_enabled,
                power_w=band.power_w,
            )
        self._bands = self._normalize_band_ends([by_slot[slot] for slot in sorted(by_slot)])
        return {"bands": len(request.bands), "verified": True}

    async def get_inverter_settings(self) -> InverterSettingsResponse:
        bands = self._normalize_band_ends(list(self._bands))
        self._bands = bands
        active_slot = active_band_index(bands)
        active = next((b for b in bands if b.slot == active_slot), bands[0] if bands else None)
        return InverterSettingsResponse(
            inverter_sn="SIM-0001",
            plant_id="sim-plant",
            plant_name="Simulator Plant",
            plant_permissions=["inverter.setting.edit"],
            write_allowed=True,
            sys_work_mode=inverter_mode_to_work_mode(self._operating_mode).value,
            sys_work_mode_label="Simulated",
            energy_mode="1",
            solar_sell=True,
            export_limit_mode="2",
            discharge_current_a=self._battery["discharge_current_a"],
            bands=list(self._bands),
            active_band_slot=active_slot,
            active_band=active,
            diagnosis="Simulator schedule.",
        )

    async def set_operating_mode(self, request: OperatingModeRequest) -> dict[str, Any]:
        self._operating_mode = request.mode
        self._last_known_good["operating_mode"] = request.mode.value
        return {"operating_mode": request.mode.value}

    async def set_battery_control(self, request: BatteryControlRequest) -> dict[str, Any]:
        applied: dict[str, int] = {}
        if request.charge_current_a is not None:
            self._battery["charge_current_a"] = request.charge_current_a
            applied["charge_current_a"] = request.charge_current_a
        if request.discharge_current_a is not None:
            self._battery["discharge_current_a"] = request.discharge_current_a
            applied["discharge_current_a"] = request.discharge_current_a
        if request.grid_charge_current_a is not None:
            self._battery["grid_charge_current_a"] = request.grid_charge_current_a
            applied["grid_charge_current_a"] = request.grid_charge_current_a
        self._last_known_good["battery"] = dict(self._battery)
        return applied

    async def force_battery(self, request: ForceBatteryRequest) -> dict[str, Any]:
        if request.action.value == "charge":
            self._battery["charge_current_a"] = 190
            self._battery["discharge_current_a"] = 0
        elif request.action.value == "discharge":
            self._battery["discharge_current_a"] = 190
            self._battery["charge_current_a"] = 0
        else:
            self._battery["charge_current_a"] = 0
            self._battery["discharge_current_a"] = 0
        self._last_known_good["battery"] = dict(self._battery)
        return {"action": request.action.value, **self._battery}

    async def get_last_known_good(self) -> Optional[dict[str, Any]]:
        return dict(self._last_known_good)
