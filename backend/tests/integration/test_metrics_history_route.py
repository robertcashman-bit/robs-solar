"""Tests for GET /metrics/history."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.db.models import MetricSampleRow
from app.db.session import SessionLocal
from tests.conftest import login


async def _seed_samples(count: int = 5) -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        for i in range(count):
            row = MetricSampleRow(
                timestamp=now - timedelta(hours=count - i),
                pv_power_w=1000.0 + i * 100,
                battery_soc_pct=50.0 + i,
                house_load_w=800.0,
                grid_import_w=100.0,
                grid_export_w=200.0,
                daily_pv_kwh=5.0,
                daily_import_kwh=1.0,
                daily_export_kwh=2.0,
                adapter_mode="simulator",
                data_source="simulated",
            )
            db.add(row)
        await db.commit()


@pytest.mark.asyncio
async def test_history_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/metrics/history?range=day")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_history_returns_series(client: AsyncClient) -> None:
    await _seed_samples(10)
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/history?range=day")
    assert response.status_code == 200
    body = response.json()
    assert body["range"] == "day"
    assert len(body["points"]) >= 1
    assert "timestamp" in body["points"][0]
    assert "pv_power_w" in body["points"][0]


@pytest.mark.asyncio
async def test_history_supports_week_and_month(client: AsyncClient) -> None:
    await _seed_samples(3)
    await login(client, "viewer", "viewer-pass")
    for range_name in ("week", "month"):
        response = await client.get(f"/metrics/history?range={range_name}")
        assert response.status_code == 200
        assert response.json()["range"] == range_name
