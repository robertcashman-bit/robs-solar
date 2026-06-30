"""Tests for GET /metrics/compare."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.db.models import MetricSampleRow
from app.db.session import SessionLocal
from tests.conftest import login


async def _seed_compare_samples() -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        for hours_ago, pv, load, imp, exp in [
            (30, 3000, 1500, 0, 500),
            (28, 2500, 1400, 200, 0),
            (26, 0, 1200, 800, 0),
            (4, 3500, 1600, 0, 600),
            (2, 3200, 1550, 100, 400),
            (1, 2800, 1500, 0, 300),
        ]:
            db.add(
                MetricSampleRow(
                    timestamp=now - timedelta(hours=hours_ago),
                    pv_power_w=float(pv),
                    battery_soc_pct=60.0,
                    house_load_w=float(load),
                    grid_import_w=float(imp),
                    grid_export_w=float(exp),
                    daily_pv_kwh=5.0,
                    daily_import_kwh=1.0,
                    daily_export_kwh=2.0,
                    adapter_mode="simulator",
                    data_source="simulated",
                )
            )
        await db.commit()


@pytest.mark.asyncio
async def test_compare_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/metrics/compare")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_compare_returns_today_and_yesterday(client: AsyncClient) -> None:
    await _seed_compare_samples()
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/compare")
    assert response.status_code == 200
    body = response.json()
    assert body["range"] == "day"
    assert "today" in body
    assert "yesterday" in body
    assert len(body["deltas"]) >= 4
    assert body["deltas"][0]["label"] == "Savings"


@pytest.mark.asyncio
async def test_compare_accepts_week_and_month(client: AsyncClient) -> None:
    await _seed_compare_samples()
    await login(client, "viewer", "viewer-pass")
    for range_name in ("week", "month"):
        response = await client.get(f"/metrics/compare?range={range_name}")
        assert response.status_code == 200
        body = response.json()
        assert body["range"] == range_name
        assert "deltas" in body
