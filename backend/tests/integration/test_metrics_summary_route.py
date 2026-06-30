"""Tests for GET /metrics/summary."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.db.models import MetricSampleRow
from app.db.session import SessionLocal
from tests.conftest import login


async def _seed_hour_of_samples() -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        # Two samples 1 hour apart: 2000W constant -> 2 kWh per channel
        for minutes in (0, 60):
            row = MetricSampleRow(
                timestamp=now - timedelta(minutes=minutes),
                pv_power_w=2000.0,
                battery_soc_pct=60.0,
                house_load_w=1500.0,
                grid_import_w=500.0,
                grid_export_w=1000.0,
                daily_pv_kwh=10.0,
                daily_import_kwh=2.0,
                daily_export_kwh=4.0,
                adapter_mode="simulator",
                data_source="simulated",
            )
            db.add(row)
        await db.commit()


@pytest.mark.asyncio
async def test_summary_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/metrics/summary?range=day")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_summary_integrates_energy_and_savings(client: AsyncClient) -> None:
    await _seed_hour_of_samples()
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/summary?range=day")
    assert response.status_code == 200
    body = response.json()
    assert body["range"] == "day"
    assert body["pv_kwh"] > 0
    assert body["consumption_kwh"] > 0
    assert body["import_kwh"] > 0
    assert body["export_kwh"] > 0
    assert 0 <= body["self_consumption_pct"] <= 100
    assert "import_cost" in body
    assert "export_credit" in body
    assert "net_cost" in body
    assert "estimated_cost_without_solar" in body
    assert "savings" in body
