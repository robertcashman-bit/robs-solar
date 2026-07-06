"""Builds the full raw-to-derived load picture for the diagnostics screen.

Combines: the adapter's raw payload (when it exposes one), the live-metrics
cache (to report live vs cached and cache age), and — if the live call fails —
the most recent database sample as a last-known-good, clearly labelled as
cached/stale.

Nothing here silently defaults an unavailable value to 0. Fields that cannot
be determined are reported with ``LoadFieldOrigin.UNKNOWN`` (or ``MISSING``
for raw payload keys that are entirely absent from the source JSON) so the UI
can say "unknown" instead of implying a real zero reading.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import InverterAdapter
from app.config import settings
from app.db.models import MetricSampleRow
from app.schemas.domain import (
    AdapterError,
    HouseLoadSource,
    LiveMetrics,
    LoadDiagnostics,
    LoadFieldOrigin,
    LoadFieldStatus,
)
from app.services.data_source import current_data_source
from app.services.effective_load import derived_house_load
from app.services.live_metrics_cache import live_metrics_cache


def _field(
    label: str,
    value: float | None,
    *,
    origin: LoadFieldOrigin,
    source_field: str | None = None,
    note: str | None = None,
) -> LoadFieldStatus:
    return LoadFieldStatus(
        label=label,
        value=value,
        origin=origin,
        source_field=source_field,
        note=note,
    )


def _power_flow_fields(
    metrics: LiveMetrics, *, origin: LoadFieldOrigin
) -> dict[str, LoadFieldStatus]:
    battery_value = metrics.battery_power_w
    battery_origin = origin if battery_value is not None else LoadFieldOrigin.UNKNOWN
    battery_note = None if battery_value is not None else "Adapter did not report battery power"
    return {
        "pv": _field("Solar (PV)", metrics.pv_power_w, origin=origin, source_field="pv_power_w"),
        "battery": _field(
            "Battery",
            battery_value,
            origin=battery_origin,
            source_field="battery_power_w",
            note=battery_note,
        ),
        "grid_import": _field(
            "Grid import", metrics.grid_import_w, origin=origin, source_field="grid_import_w"
        ),
        "grid_export": _field(
            "Grid export", metrics.grid_export_w, origin=origin, source_field="grid_export_w"
        ),
    }


def _sample_to_fields(sample: MetricSampleRow) -> dict[str, LoadFieldStatus]:
    origin = LoadFieldOrigin.CACHED
    battery_value = sample.battery_power_w
    return {
        "pv": _field("Solar (PV)", sample.pv_power_w, origin=origin, source_field="pv_power_w"),
        "battery": _field(
            "Battery",
            battery_value,
            origin=origin if battery_value is not None else LoadFieldOrigin.UNKNOWN,
            source_field="battery_power_w",
            note=None if battery_value is not None else "Last sample had no battery power",
        ),
        "grid_import": _field(
            "Grid import", sample.grid_import_w, origin=origin, source_field="grid_import_w"
        ),
        "grid_export": _field(
            "Grid export", sample.grid_export_w, origin=origin, source_field="grid_export_w"
        ),
    }


def _raw_payload_from_adapter(
    adapter: InverterAdapter,
) -> tuple[dict | None, datetime | None, str | None]:
    """Best-effort raw payload from adapters that expose one (currently Sunsynk).

    Returns (raw_payload, captured_at, note). Never fabricates a payload for
    adapters that don't have one (simulator/Modbus/HA) — reports a clear note
    instead.
    """
    get_diagnostics = getattr(adapter, "get_load_diagnostics", None)
    if get_diagnostics is None:
        return None, None, "This adapter does not expose a raw cloud/API payload."
    snapshot = get_diagnostics()
    if snapshot is None:
        return None, None, "No raw payload captured yet — live metrics have not been fetched."
    return snapshot.get("raw_payload"), snapshot.get("captured_at"), None


class LoadDiagnosticsService:
    async def get_diagnostics(
        self,
        adapter: InverterAdapter,
        db: AsyncSession | None = None,
    ) -> LoadDiagnostics:
        now = datetime.now(timezone.utc)
        adapter_mode = settings.adapter_mode
        data_source = current_data_source()

        cached_metrics = live_metrics_cache.peek()
        metrics: LiveMetrics | None = cached_metrics
        is_cached = cached_metrics is not None
        cache_age_seconds = live_metrics_cache.age_seconds() if cached_metrics is not None else None
        stale_note: str | None = None

        if metrics is None:
            try:
                metrics = await adapter.get_live_metrics()
                is_cached = False
                cache_age_seconds = 0.0
            except AdapterError as exc:
                metrics = None
                stale_note = f"Live fetch failed ({exc}); showing last known database sample."

        raw_payload, raw_payload_captured_at, raw_payload_note = _raw_payload_from_adapter(adapter)

        if metrics is not None:
            field_origin = LoadFieldOrigin.LIVE if not is_cached else LoadFieldOrigin.CACHED
            fields = _power_flow_fields(metrics, origin=field_origin)
            house_load_w = metrics.house_load_w
            house_load_source = metrics.house_load_source
            house_load_at = metrics.house_load_at
            grid_meter_connected = metrics.grid_meter_connected
            measured_load_w = metrics.house_load_reported_w
            measured_origin = (
                LoadFieldOrigin.LIVE
                if house_load_source == HouseLoadSource.REPORTED and not is_cached
                else LoadFieldOrigin.CACHED
                if house_load_source == HouseLoadSource.REPORTED
                else LoadFieldOrigin.UNKNOWN
            )
            estimated_load_w = derived_house_load(
                pv=metrics.pv_power_w,
                grid_import=metrics.grid_import_w,
                grid_export=metrics.grid_export_w,
                battery_power_w=metrics.battery_power_w or 0.0,
            )
        else:
            sample = None
            if db is not None:
                sample = await db.scalar(
                    select(MetricSampleRow).order_by(MetricSampleRow.timestamp.desc()).limit(1)
                )
            if sample is not None:
                fields = _sample_to_fields(sample)
                house_load_w = sample.house_load_w
                house_load_source = HouseLoadSource.MINIMAL
                house_load_at = sample.timestamp
                grid_meter_connected = None
                measured_load_w = None
                measured_origin = LoadFieldOrigin.UNKNOWN
                estimated_load_w = derived_house_load(
                    pv=sample.pv_power_w,
                    grid_import=sample.grid_import_w,
                    grid_export=sample.grid_export_w,
                    battery_power_w=sample.battery_power_w or 0.0,
                )
                is_cached = True
                cache_age_seconds = (
                    (now - sample.timestamp.replace(tzinfo=timezone.utc)).total_seconds()
                    if sample.timestamp.tzinfo is None
                    else (now - sample.timestamp).total_seconds()
                )
                stale_note = (
                    stale_note or "Showing last known database sample (live fetch unavailable)."
                )
            else:
                unknown = _field("Unknown", None, origin=LoadFieldOrigin.UNKNOWN)
                fields = {
                    "pv": unknown,
                    "battery": unknown,
                    "grid_import": unknown,
                    "grid_export": unknown,
                }
                house_load_w = 0.0
                house_load_source = HouseLoadSource.MINIMAL
                house_load_at = None
                grid_meter_connected = None
                measured_load_w = None
                measured_origin = LoadFieldOrigin.UNKNOWN
                estimated_load_w = None
                stale_note = stale_note or "No live data and no database sample available."

        combined_note = " ".join(note for note in (stale_note, raw_payload_note) if note) or None

        return LoadDiagnostics(
            timestamp=now,
            adapter_mode=adapter_mode,
            data_source=data_source,
            is_cached=is_cached,
            cache_age_seconds=cache_age_seconds,
            raw_payload=raw_payload,
            raw_payload_captured_at=raw_payload_captured_at,
            raw_payload_note=combined_note,
            pv=fields["pv"],
            battery=fields["battery"],
            grid_import=fields["grid_import"],
            grid_export=fields["grid_export"],
            measured_load_w=measured_load_w,
            measured_load_origin=measured_origin,
            estimated_load_w=estimated_load_w,
            house_load_source=house_load_source,
            house_load_w=house_load_w,
            house_load_at=house_load_at,
            grid_meter_connected=grid_meter_connected,
        )


load_diagnostics_service = LoadDiagnosticsService()
