"""Analytics applies live Octopus import AND export rates when configured."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models import MetricSampleRow
from app.db.session import SessionLocal
from app.schemas.domain import HistoryRange
from app.services import analytics_service as analytics_module
from app.services.analytics_service import analytics_service


async def _seed() -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        await db.execute(delete(MetricSampleRow))
        for minutes in (0, 60):
            db.add(
                MetricSampleRow(
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
            )
        await db.commit()


@pytest.mark.asyncio
async def test_summary_uses_octopus_import_and_export_overrides(monkeypatch) -> None:
    await _seed()
    client = analytics_module.octopus_client
    monkeypatch.setattr(client, "configured", lambda: True)

    async def fake_import() -> float:
        return 0.30

    async def fake_export() -> float:
        return 0.10

    monkeypatch.setattr(client, "get_import_rate_gbp", fake_import)
    monkeypatch.setattr(client, "get_export_rate_gbp", fake_export)

    async with SessionLocal() as db:
        summary = await analytics_service.get_summary(db, HistoryRange.DAY)

    assert summary.import_cost == pytest.approx(round(summary.import_kwh * 0.30, 2))
    assert summary.export_credit == pytest.approx(round(summary.export_kwh * 0.10, 2))


@pytest.mark.asyncio
async def test_summary_falls_back_to_stored_tariff_when_unconfigured(monkeypatch) -> None:
    await _seed()
    client = analytics_module.octopus_client
    monkeypatch.setattr(client, "configured", lambda: False)

    async with SessionLocal() as db:
        tariff = await analytics_module.tariff_service.get_tariff(db)
        summary = await analytics_service.get_summary(db, HistoryRange.DAY)

    assert summary.import_cost == pytest.approx(round(summary.import_kwh * tariff.import_rate, 2))
    assert summary.export_credit == pytest.approx(round(summary.export_kwh * tariff.export_rate, 2))
