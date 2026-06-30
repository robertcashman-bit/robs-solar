"""Tests for background metric sampler."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.adapters.simulator import SimulatorAdapter
from app.db.models import MetricSampleRow
from app.db.session import SessionLocal
from app.services.metric_sampler import record_sample


@pytest.mark.asyncio
async def test_record_sample_persists_metrics() -> None:
    adapter = SimulatorAdapter()
    metrics = await adapter.get_live_metrics()
    await record_sample(metrics, adapter_mode="simulator", data_source="simulated")

    async with SessionLocal() as db:
        result = await db.execute(
            select(MetricSampleRow).order_by(MetricSampleRow.id.desc()).limit(1)
        )
        row = result.scalar_one()
        assert row.pv_power_w == metrics.pv_power_w
        assert row.battery_soc_pct == metrics.battery_soc_pct
        assert row.adapter_mode == "simulator"
        assert row.data_source == "simulated"


@pytest.mark.asyncio
async def test_sampler_swallows_adapter_errors() -> None:
    from app.services import metric_sampler

    failing = AsyncMock(side_effect=Exception("adapter down"))
    with patch.object(metric_sampler, "get_adapter") as mock_factory:
        mock_adapter = AsyncMock()
        mock_adapter.get_live_metrics = failing
        mock_factory.return_value = mock_adapter
        # Should not raise
        await metric_sampler.sample_once()
