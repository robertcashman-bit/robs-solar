"""Unit tests for LoadDiagnosticsService.

Covers: live raw payload passthrough, graceful degradation for adapters with
no raw payload, live-metrics-cache reporting, and last-known-good database
fallback when the live call fails -- always labelling unavailable fields as
"unknown"/"cached", never silently substituting 0.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.adapters.simulator import SimulatorAdapter
from app.db.models import MetricSampleRow
from app.db.session import SessionLocal
from app.schemas.domain import (
    AdapterError,
    HouseLoadSource,
    InverterMode,
    InverterStatus,
    LiveMetrics,
    LoadFieldOrigin,
)
from app.services.live_metrics_cache import live_metrics_cache
from app.services.load_diagnostics_service import LoadDiagnosticsService


@pytest.fixture(autouse=True)
def _reset_cache():
    live_metrics_cache._metrics = None
    live_metrics_cache._fetched_at = None
    yield
    live_metrics_cache._metrics = None
    live_metrics_cache._fetched_at = None


class _FakeSunsynkLikeAdapter:
    """Minimal stand-in exposing the same get_load_diagnostics() shape as
    SunsynkConnectAdapter, without any real HTTP/auth machinery."""

    def __init__(self, metrics: LiveMetrics, raw_diagnostics: dict | None) -> None:
        self._metrics = metrics
        self._raw_diagnostics = raw_diagnostics
        self.calls = 0

    async def get_live_metrics(self) -> LiveMetrics:
        self.calls += 1
        return self._metrics

    def get_load_diagnostics(self) -> dict | None:
        return self._raw_diagnostics


class _FailingAdapter:
    async def get_live_metrics(self) -> LiveMetrics:
        raise AdapterError("Sunsynk request failed: timeout")


def _metrics(**overrides) -> LiveMetrics:
    base = dict(
        pv_power_w=33.0,
        battery_soc_pct=99.0,
        battery_power_w=143.0,
        house_load_w=188.0,
        house_load_source=HouseLoadSource.DERIVED,
        house_load_reported_w=0.0,
        grid_import_w=12.0,
        grid_export_w=0.0,
        inverter_mode=InverterMode.SELF_USE,
        inverter_status=InverterStatus.ONLINE,
        daily_pv_kwh=0.005,
        daily_import_kwh=4.391,
        daily_export_kwh=0.0,
        timestamp=datetime.now(timezone.utc),
        grid_meter_connected=False,
    )
    base.update(overrides)
    return LiveMetrics(**base)


@pytest.mark.asyncio
async def test_live_payload_passthrough_for_sunsynk_like_adapter() -> None:
    raw = {
        "raw_payload": {"pvPower": 33, "loadOrEpsPower": 0, "gridOrMeterPower": 12},
        "captured_at": datetime.now(timezone.utc),
        "field_presence": {"loadOrEpsPower": True, "upsLoadPower": False},
        "field_raw_values": {"loadOrEpsPower": 0, "upsLoadPower": None},
    }
    adapter = _FakeSunsynkLikeAdapter(_metrics(), raw)
    service = LoadDiagnosticsService()
    diagnostics = await service.get_diagnostics(adapter, db=None)

    assert diagnostics.raw_payload == raw["raw_payload"]
    assert diagnostics.raw_payload_note is None
    assert diagnostics.is_cached is False
    assert diagnostics.pv.origin == LoadFieldOrigin.LIVE
    assert diagnostics.pv.value == pytest.approx(33.0)
    assert diagnostics.grid_import.value == pytest.approx(12.0)
    assert diagnostics.house_load_w == pytest.approx(188.0)
    assert diagnostics.house_load_source == HouseLoadSource.DERIVED
    # Measured (raw CT) and estimated (balance) must stay separate and both present.
    assert diagnostics.measured_load_w == pytest.approx(0.0)
    assert diagnostics.estimated_load_w == pytest.approx(33.0 + 12.0 - 0.0 + 143.0)
    assert diagnostics.grid_meter_connected is False


@pytest.mark.asyncio
async def test_adapter_without_raw_payload_reports_unavailable_not_zero() -> None:
    adapter = SimulatorAdapter()
    service = LoadDiagnosticsService()
    diagnostics = await service.get_diagnostics(adapter, db=None)

    assert diagnostics.raw_payload is None
    assert diagnostics.raw_payload_note is not None
    assert "does not expose" in diagnostics.raw_payload_note
    # Simulator still reports real numbers for the power-flow fields (not "unavailable").
    assert diagnostics.pv.origin == LoadFieldOrigin.LIVE
    assert diagnostics.pv.value is not None


@pytest.mark.asyncio
async def test_uses_live_metrics_cache_when_fresh() -> None:
    cached = _metrics(house_load_w=250.0)
    live_metrics_cache._metrics = cached
    live_metrics_cache._fetched_at = datetime.now(timezone.utc)

    adapter = _FakeSunsynkLikeAdapter(_metrics(house_load_w=999.0), None)
    service = LoadDiagnosticsService()
    diagnostics = await service.get_diagnostics(adapter, db=None)

    # Must come from the cache, not a fresh adapter call.
    assert adapter.calls == 0
    assert diagnostics.is_cached is True
    assert diagnostics.cache_age_seconds is not None
    assert diagnostics.cache_age_seconds < 1.0
    assert diagnostics.house_load_w == pytest.approx(250.0)
    assert diagnostics.pv.origin == LoadFieldOrigin.CACHED


@pytest.mark.asyncio
async def test_falls_back_to_last_db_sample_when_live_fetch_fails() -> None:
    from app.services.metric_sampler import record_sample

    async with SessionLocal() as db:
        await db.execute(delete(MetricSampleRow))
        await db.commit()

    metrics = _metrics(house_load_w=777.0, pv_power_w=10.0, grid_import_w=800.0)
    await record_sample(metrics, adapter_mode="sunsynk_connect", data_source="live")

    adapter = _FailingAdapter()
    service = LoadDiagnosticsService()
    async with SessionLocal() as db:
        diagnostics = await service.get_diagnostics(adapter, db=db)

    assert diagnostics.is_cached is True
    assert diagnostics.raw_payload is None
    assert diagnostics.raw_payload_note is not None
    assert "database sample" in diagnostics.raw_payload_note.lower()
    assert diagnostics.pv.origin == LoadFieldOrigin.CACHED
    assert diagnostics.pv.value == pytest.approx(10.0)
    assert diagnostics.grid_import.value == pytest.approx(800.0)
    # Measured load is unknown from a bare DB row (we didn't persist house_load_reported_w).
    assert diagnostics.measured_load_origin == LoadFieldOrigin.UNKNOWN
    assert diagnostics.measured_load_w is None
    # Estimated (derived) load can still be computed from the stored power-flow fields.
    assert diagnostics.estimated_load_w is not None


@pytest.mark.asyncio
async def test_no_live_data_and_no_db_sample_reports_unknown_not_zero() -> None:
    async with SessionLocal() as db:
        await db.execute(delete(MetricSampleRow))
        await db.commit()

    adapter = _FailingAdapter()
    service = LoadDiagnosticsService()
    async with SessionLocal() as db:
        diagnostics = await service.get_diagnostics(adapter, db=db)

    assert diagnostics.pv.origin == LoadFieldOrigin.UNKNOWN
    assert diagnostics.pv.value is None
    assert diagnostics.battery.origin == LoadFieldOrigin.UNKNOWN
    assert diagnostics.grid_import.origin == LoadFieldOrigin.UNKNOWN
    assert diagnostics.estimated_load_w is None
    assert diagnostics.measured_load_w is None
    assert diagnostics.raw_payload_note is not None
