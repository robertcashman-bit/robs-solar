"""Tests for live metrics cache."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.schemas.domain import InverterMode, InverterStatus, LiveMetrics
from app.services.live_metrics_cache import LiveMetricsCache


def _sample_metrics() -> LiveMetrics:
    return LiveMetrics(
        pv_power_w=1000,
        battery_soc_pct=80,
        house_load_w=500,
        grid_import_w=0,
        grid_export_w=200,
        inverter_mode=InverterMode.SELF_USE,
        inverter_status=InverterStatus.ONLINE,
        daily_pv_kwh=12.0,
        daily_import_kwh=3.0,
        daily_export_kwh=5.0,
        timestamp=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_cache_reuses_fresh_metrics() -> None:
    cache = LiveMetricsCache()
    adapter = AsyncMock()
    adapter.get_live_metrics = AsyncMock(return_value=_sample_metrics())

    first = await cache.get(adapter)
    second = await cache.get(adapter)

    assert first.daily_pv_kwh == 12.0
    assert second.daily_pv_kwh == 12.0
    adapter.get_live_metrics.assert_awaited_once()
