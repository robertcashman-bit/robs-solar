"""Battery discharge behaviour tests (root-cause coverage for "stuck at ~95%").

Each class maps to a lettered scenario from the investigation brief:
A overnight charging, B daytime discharge, C minimum SOC, D 95% regression,
E timezone, H sign convention, I scheduler conflict. API-failure (F), restart
(G) and persistence (J) live in tests/integration/test_battery_plan_route.py and
test_auto_schedule_restart.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from pydantic import ValidationError

from app.adapters.sunsynk_connect import SunsynkConnectAdapter
from app.config import settings
from app.schemas.domain import (
    AutoScheduleConfigRequest,
    DispatchWindow,
    InverterMode,
    SystemWorkMode,
    TouBand,
)
from app.services.charge_window_service import evaluate_charge_window
from app.services.iog_schedule import (
    charge_intervals_from_windows,
    compute_iog_bands,
    is_charge_minute,
)
from app.services.peak_import_guard_service import should_remediate
from app.services.schedule_validation import errors_only, validate_schedule_config

OFFPEAK_START = "23:30"
OFFPEAK_END = "05:30"


def _band_covering(bands, minute: int):
    """Return the band whose [start, next-start) window contains *minute*."""
    parsed = sorted((int(b.start[:2]) * 60 + int(b.start[3:]), b) for b in bands)
    chosen = parsed[-1][1]
    for start_min, band in parsed:
        if start_min <= minute:
            chosen = band
    return chosen


# ---------------------------------------------------------------------------
# A. Overnight cheap-rate charging
# ---------------------------------------------------------------------------
class TestOvernightCharging:
    def test_overnight_band_charges_to_target(self) -> None:
        bands = compute_iog_bands(
            offpeak_start=OFFPEAK_START,
            offpeak_end=OFFPEAK_END,
            planned=[],
            soc_floor_pct=20,
            overnight_target_pct=100,
        )
        overnight = _band_covering(bands, 2 * 60)  # 02:00 is inside 23:30-05:30
        assert overnight.grid_charge_enabled is True
        assert overnight.target_soc_pct == 100

    def test_slot_one_starts_at_midnight(self) -> None:
        bands = compute_iog_bands(
            offpeak_start=OFFPEAK_START,
            offpeak_end=OFFPEAK_END,
            planned=[],
            soc_floor_pct=20,
        )
        assert bands[0].start == "00:00"


# ---------------------------------------------------------------------------
# B. Daytime discharge
# ---------------------------------------------------------------------------
class TestDaytimeDischarge:
    def test_daytime_band_discharges_grid_off(self) -> None:
        bands = compute_iog_bands(
            offpeak_start=OFFPEAK_START,
            offpeak_end=OFFPEAK_END,
            planned=[],
            soc_floor_pct=20,
            overnight_target_pct=100,
        )
        daytime = _band_covering(bands, 12 * 60)  # midday
        assert daytime.grid_charge_enabled is False
        assert daytime.target_soc_pct == 20

    def test_peak_import_at_95pct_flags_problem(self) -> None:
        # SOC 95%, load > solar, importing, battery barely moving -> peak_import
        now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        status = evaluate_charge_window(
            grid_import_w=900.0,
            battery_soc_pct=95.0,
            battery_power_w=0.0,
            active_band=TouBand(
                slot=2, start="05:30", end="23:30", target_soc_pct=20,
                grid_charge_enabled=False, power_w=8000,
            ),
            offpeak_start=OFFPEAK_START,
            offpeak_end=OFFPEAK_END,
            planned=[],
            now=now,
        )
        assert status.state == "peak_import"
        assert status.cheap_now is False

    def test_guard_would_remediate_daytime_import_at_high_soc(self) -> None:
        assert should_remediate(
            cheap_now=False,
            grid_import_w=900.0,
            battery_soc_pct=95.0,
            battery_power_w=0.0,
            soc_floor_pct=20,
            import_threshold_w=100.0,
        )


# ---------------------------------------------------------------------------
# C. Minimum SOC — discharge from 95% down towards 20%, never treat 95 as reserve
# ---------------------------------------------------------------------------
class TestMinimumSoc:
    def test_daytime_floor_is_configured_value_not_95(self) -> None:
        for floor in (10, 20, 30):
            bands = compute_iog_bands(
                offpeak_start=OFFPEAK_START,
                offpeak_end=OFFPEAK_END,
                planned=[],
                soc_floor_pct=floor,
            )
            daytime = _band_covering(bands, 13 * 60)
            assert daytime.target_soc_pct == floor

    def test_95pct_not_treated_as_reserve(self) -> None:
        # At 95% with a 20% floor and a discharge-capable daytime band, the
        # battery has 75% of headroom to discharge; charge_window must not say
        # it is at reserve.
        status = evaluate_charge_window(
            grid_import_w=600.0,
            battery_soc_pct=95.0,
            battery_power_w=0.0,
            active_band=TouBand(
                slot=2, start="05:30", end="23:30", target_soc_pct=20,
                grid_charge_enabled=False, power_w=8000,
            ),
            offpeak_start=OFFPEAK_START,
            offpeak_end=OFFPEAK_END,
            planned=[],
            now=datetime(2026, 1, 15, 14, 0, tzinfo=timezone.utc),
        )
        assert status.state == "peak_import"  # problem flagged, not "at reserve / idle"


# ---------------------------------------------------------------------------
# D. 95% regression — no hardcoded 95 reserve anywhere in the schedule builder
# ---------------------------------------------------------------------------
class TestNinetyFiveRegression:
    def test_no_band_defaults_to_95(self) -> None:
        bands = compute_iog_bands(
            offpeak_start=OFFPEAK_START,
            offpeak_end=OFFPEAK_END,
            planned=[],
            soc_floor_pct=20,
        )
        assert all(b.target_soc_pct in (20, 100) for b in bands)
        assert all(b.target_soc_pct != 95 for b in bands)

    def test_config_rejects_floor_at_95(self) -> None:
        with pytest.raises(ValidationError):
            AutoScheduleConfigRequest(enabled=True, soc_floor_pct=95)

    def test_validation_flags_floor_at_or_above_95(self) -> None:
        issues = validate_schedule_config(
            daytime_floor_pct=95,
            overnight_target_pct=100,
            offpeak_start=OFFPEAK_START,
            offpeak_end=OFFPEAK_END,
            tariff_timezone="Europe/London",
        )
        assert any(i.code == "floor_too_high" for i in errors_only(issues))

    def test_validation_flags_target_below_floor(self) -> None:
        issues = validate_schedule_config(
            daytime_floor_pct=80,
            overnight_target_pct=50,
            offpeak_start=OFFPEAK_START,
            offpeak_end=OFFPEAK_END,
            tariff_timezone="Europe/London",
        )
        assert any(i.code == "target_below_floor" for i in errors_only(issues))


# ---------------------------------------------------------------------------
# E. Timezone — windows computed in tariff timezone, not server/UTC, with DST
# ---------------------------------------------------------------------------
class TestTimezone:
    def _cheap(self, now: datetime) -> bool:
        return evaluate_charge_window(
            grid_import_w=0.0,
            battery_soc_pct=50.0,
            battery_power_w=0.0,
            active_band=None,
            offpeak_start=OFFPEAK_START,
            offpeak_end=OFFPEAK_END,
            planned=[],
            now=now,
        ).cheap_now

    def test_same_instant_differs_by_tariff_timezone(self, monkeypatch) -> None:
        instant = datetime(2026, 1, 15, 6, 0, tzinfo=timezone.utc)
        monkeypatch.setattr(settings, "tariff_timezone", "Europe/London")
        assert self._cheap(instant) is False  # 06:00 GMT -> peak
        # UTC-3 (no DST): 06:00Z -> 03:00 local -> inside 23:30-05:30 cheap window
        monkeypatch.setattr(settings, "tariff_timezone", "America/Argentina/Buenos_Aires")
        assert self._cheap(instant) is True

    def test_dst_shift_changes_window_boundary(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "tariff_timezone", "Europe/London")
        # 04:45Z: winter (GMT) -> 04:45 local (cheap); summer (BST) -> 05:45 (peak)
        assert self._cheap(datetime(2026, 1, 1, 4, 45, tzinfo=timezone.utc)) is True
        assert self._cheap(datetime(2026, 7, 1, 4, 45, tzinfo=timezone.utc)) is False

    def test_invalid_timezone_falls_back(self, monkeypatch) -> None:
        monkeypatch.setattr(settings, "tariff_timezone", "Not/AZone")
        # Falls back to Europe/London rather than raising
        assert self._cheap(datetime(2026, 1, 15, 6, 0, tzinfo=timezone.utc)) is False


# ---------------------------------------------------------------------------
# H. Sign convention — battery charge/discharge and grid import/export
# ---------------------------------------------------------------------------
class TestSignConvention:
    def _adapter(self) -> SunsynkConnectAdapter:
        return SunsynkConnectAdapter(client=httpx.AsyncClient())

    def test_battery_direction_flag_charging_is_negative(self) -> None:
        m = self._adapter()._parse_flow(
            {"data": {"battPower": 600, "toBat": True, "soc": 80,
                      "pvPower": 0, "loadOrEpsPower": 100, "gridOrMeterPower": 0}}
        )
        assert m.battery_power_w == -600  # charging -> negative (app convention)

    def test_battery_direction_flag_discharging_is_positive(self) -> None:
        m = self._adapter()._parse_flow(
            {"data": {"battPower": 600, "batteryTo": True, "soc": 80,
                      "pvPower": 0, "loadOrEpsPower": 700, "gridOrMeterPower": 0}}
        )
        assert m.battery_power_w == 600  # discharging -> positive

    def test_battery_signed_negative_is_discharging(self) -> None:
        m = self._adapter()._parse_flow(
            {"data": {"battPower": -158, "soc": 98,
                      "pvPower": 85, "loadOrEpsPower": 0, "gridOrMeterPower": 12}}
        )
        assert m.battery_power_w == 158
        assert m.house_load_w == pytest.approx(255, abs=5)

    def test_battery_signed_fallback_without_flags(self) -> None:
        m = self._adapter()._parse_flow(
            {"data": {"battPower": 600, "soc": 80,
                      "pvPower": 0, "loadOrEpsPower": 100, "gridOrMeterPower": 0}}
        )
        assert m.battery_power_w == 600  # unchanged legacy behaviour

    def test_grid_direction_flags(self) -> None:
        adapter = self._adapter()
        imp = adapter._parse_flow(
            {"data": {"gridOrMeterPower": 2400, "gridTo": True, "soc": 50,
                      "pvPower": 0, "loadOrEpsPower": 2400, "battPower": 0}}
        )
        assert imp.grid_import_w == 2400 and imp.grid_export_w == 0
        exp = adapter._parse_flow(
            {"data": {"gridOrMeterPower": 2400, "toGrid": True, "soc": 50,
                      "pvPower": 4800, "loadOrEpsPower": 2400, "battPower": 0}}
        )
        assert exp.grid_export_w == 2400 and exp.grid_import_w == 0

    def test_grid_signed_fallback(self) -> None:
        # Negative gridOrMeterPower without flags -> export (legacy behaviour)
        m = self._adapter()._parse_flow(
            {"data": {"gridOrMeterPower": -2400, "soc": 50,
                      "pvPower": 4800, "loadOrEpsPower": 2400, "battPower": 0}}
        )
        assert m.grid_export_w == 2400 and m.grid_import_w == 0

    def test_work_mode_selling_maps_to_feed_in(self) -> None:
        m = self._adapter()._parse_flow(
            {"data": {"sysWorkMode": "2", "soc": 96, "pvPower": 30,
                      "loadOrEpsPower": 970, "gridOrMeterPower": 20, "battPower": 0}}
        )
        assert m.inverter_mode == InverterMode.FEED_IN
        assert m.system_work_mode == SystemWorkMode.SELLING


# ---------------------------------------------------------------------------
# I. Scheduler conflict — night charge and day discharge never overlap
# ---------------------------------------------------------------------------
class TestSchedulerConflict:
    def test_charge_and_discharge_never_overlap(self) -> None:
        charge = charge_intervals_from_windows(OFFPEAK_START, OFFPEAK_END, [])
        # Cheap minute charges, daytime minute does not — mutually exclusive.
        assert is_charge_minute(2 * 60, charge) is True  # 02:00
        assert is_charge_minute(12 * 60, charge) is False  # 12:00

    def test_adjacent_bands_alternate_grid_charge(self) -> None:
        bands = compute_iog_bands(
            offpeak_start=OFFPEAK_START,
            offpeak_end=OFFPEAK_END,
            planned=[],
            soc_floor_pct=20,
        )
        for left, right in zip(bands, bands[1:]):
            assert left.grid_charge_enabled != right.grid_charge_enabled

    def test_planned_dispatch_added_as_charge_window(self) -> None:
        planned = [
            DispatchWindow(
                start=datetime(2026, 1, 15, 12, 1, tzinfo=timezone.utc),
                end=datetime(2026, 1, 15, 12, 30, tzinfo=timezone.utc),
                source="smart-charge",
            )
        ]
        charge = charge_intervals_from_windows(
            OFFPEAK_START, OFFPEAK_END, planned,
            now=datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc),
        )
        # The dispatch window should register as a charge interval at its local time.
        local_minute = 12 * 60 + 15
        assert is_charge_minute(local_minute, charge) is True
