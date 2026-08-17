"""Day-range analytics aligned with Sunsynk etoday counters."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.domain import HistoryRange, LiveMetrics, MetricSummaryResponse
from app.services.analytics_service import _range_start, enrich_day_summary_with_live
from app.services.tariff_clock import tariff_now


def test_day_range_starts_at_local_midnight() -> None:
    start = _range_start(HistoryRange.DAY)
    local_midnight = tariff_now().replace(hour=0, minute=0, second=0, microsecond=0)
    expected = local_midnight.astimezone(timezone.utc)
    assert start == expected


@pytest.mark.asyncio
async def test_enrich_day_summary_with_live_overlays_etoday() -> None:
    from app.db.session import SessionLocal

    summary = MetricSummaryResponse(
        range=HistoryRange.DAY,
        pv_kwh=1.0,
        consumption_kwh=2.0,
        import_kwh=0.5,
        export_kwh=0.2,
        self_consumption_pct=80.0,
        import_cost=0.15,
        export_credit=0.03,
        net_cost=0.12,
        estimated_cost_without_solar=0.40,
        savings=0.28,
        currency="GBP",
    )
    live = LiveMetrics(
        pv_power_w=1000,
        battery_soc_pct=90,
        house_load_w=500,
        grid_import_w=0,
        grid_export_w=100,
        inverter_mode="self_use",
        inverter_status="online",
        daily_pv_kwh=12.4,
        daily_import_kwh=3.1,
        daily_export_kwh=5.8,
        timestamp=datetime.now(timezone.utc),
    )
    async with SessionLocal() as db:
        enriched = await enrich_day_summary_with_live(db, summary, live)
    assert enriched.pv_kwh == pytest.approx(12.4)
    assert enriched.import_kwh == pytest.approx(3.1)
    assert enriched.export_kwh == pytest.approx(5.8)
    assert enriched.self_consumption_pct == pytest.approx(53.2, abs=0.1)
