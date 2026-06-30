"""Background metric sampler — persists live readings for analytics."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete

from app.adapters.factory import get_adapter
from app.config import settings
from app.db.models import MetricSampleRow
from app.db.session import SessionLocal
from app.schemas.domain import AdapterError, LiveMetrics

logger = logging.getLogger(__name__)

_sampler_task: Optional[asyncio.Task] = None


async def record_sample(
    metrics: LiveMetrics,
    *,
    adapter_mode: str,
    data_source: str,
) -> None:
    async with SessionLocal() as db:
        row = MetricSampleRow(
            timestamp=metrics.timestamp,
            pv_power_w=metrics.pv_power_w,
            battery_soc_pct=metrics.battery_soc_pct,
            house_load_w=metrics.house_load_w,
            grid_import_w=metrics.grid_import_w,
            grid_export_w=metrics.grid_export_w,
            daily_pv_kwh=metrics.daily_pv_kwh,
            daily_import_kwh=metrics.daily_import_kwh,
            daily_export_kwh=metrics.daily_export_kwh,
            adapter_mode=adapter_mode,
            data_source=data_source,
            pv1_power_w=metrics.pv1_power_w,
            pv2_power_w=metrics.pv2_power_w,
            battery_power_w=metrics.battery_power_w,
            battery_voltage_v=metrics.battery_voltage_v,
            battery_current_a=metrics.battery_current_a,
            battery_temp_c=metrics.battery_temp_c,
            battery_soh_pct=metrics.battery_soh_pct,
            grid_voltage_v=metrics.grid_voltage_v,
            grid_frequency_hz=metrics.grid_frequency_hz,
            daily_battery_charge_kwh=metrics.daily_battery_charge_kwh,
            daily_battery_discharge_kwh=metrics.daily_battery_discharge_kwh,
        )
        db.add(row)
        await db.commit()


async def sample_once() -> None:
    try:
        adapter = get_adapter()
        metrics = await adapter.get_live_metrics()
        data_source = "simulated" if settings.adapter_mode.lower() == "simulator" else "live"
        await record_sample(
            metrics,
            adapter_mode=settings.adapter_mode,
            data_source=data_source,
        )
        async with SessionLocal() as db:
            from app.services.alert_service import alert_service
            from app.services.ev_load_detector import ev_load_detector
            from app.services.octopus_client import octopus_client
            from app.services.peak_import_guard_service import peak_import_guard_service
            from app.services.rules_engine import rules_engine

            await alert_service.evaluate(db, metrics)
            try:
                dispatches = await octopus_client.get_dispatches()
                ev_load_detector.update(metrics, list(dispatches.planned))
            except Exception:
                ev_load_detector.update(metrics)
            await rules_engine.evaluate(db, metrics)
            await peak_import_guard_service.evaluate(db, metrics, adapter)
    except (AdapterError, Exception) as exc:
        logger.warning("Metric sample failed: %s", exc)


async def prune_old_samples() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.metrics_retention_days)
    async with SessionLocal() as db:
        await db.execute(delete(MetricSampleRow).where(MetricSampleRow.timestamp < cutoff))
        await db.commit()


async def _sampler_loop() -> None:
    prune_counter = 0
    while True:
        await sample_once()
        prune_counter += 1
        if prune_counter >= 60:
            await prune_old_samples()
            prune_counter = 0
        await asyncio.sleep(settings.metrics_sample_interval_seconds)


def start_sampler() -> Optional[asyncio.Task]:
    global _sampler_task
    if not settings.metrics_sampler_enabled:
        return None
    if _sampler_task is not None and not _sampler_task.done():
        return _sampler_task
    _sampler_task = asyncio.create_task(_sampler_loop())
    return _sampler_task


async def stop_sampler() -> None:
    global _sampler_task
    if _sampler_task is not None:
        _sampler_task.cancel()
        try:
            await _sampler_task
        except asyncio.CancelledError:
            pass
        _sampler_task = None
