"""Analytics applies live Octopus import AND export rates when configured."""

from datetime import timedelta, timezone

import pytest
from sqlalchemy import delete

from app.db.models import MetricSampleRow
from app.db.session import SessionLocal
from app.schemas.domain import HistoryRange
from app.services import analytics_service as analytics_module
from app.services.analytics_service import analytics_service
from app.services.tariff_clock import tariff_now


async def _seed() -> None:
    # Seed a one-hour afternoon interval in the tariff timezone. Samples at
    # datetime.now(UTC) fall into the 23:30–05:30 off-peak window after 22:30 UTC
    # during British Summer Time, and those kWh are billed at night_import_rate
    # instead of the Octopus/day override these tests assert.
    local_afternoon = tariff_now().replace(hour=14, minute=0, second=0, microsecond=0)
    later = local_afternoon.astimezone(timezone.utc)
    earlier = later - timedelta(hours=1)
    async with SessionLocal() as db:
        await db.execute(delete(MetricSampleRow))
        for timestamp in (earlier, later):
            db.add(
                MetricSampleRow(
                    timestamp=timestamp,
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
        tariff = await analytics_module.tariff_service.get_tariff(db)
        summary = await analytics_service.get_summary(db, HistoryRange.DAY)

    assert summary.import_kwh > 0
    assert summary.export_kwh > 0
    assert summary.breakdown is not None
    assert summary.breakdown.import_rate_gbp == pytest.approx(0.30)
    assert summary.breakdown.export_rate_gbp == pytest.approx(0.10)
    night_rate = tariff.night_import_rate if tariff.night_import_rate is not None else 0.30
    assert summary.import_cost == pytest.approx(
        round(
            summary.breakdown.cheap_import_kwh * night_rate
            + summary.breakdown.peak_import_kwh * 0.30,
            2,
        )
    )
    assert summary.export_credit == pytest.approx(round(summary.export_kwh * 0.10, 2))


@pytest.mark.asyncio
async def test_summary_falls_back_to_stored_tariff_when_unconfigured(monkeypatch) -> None:
    await _seed()
    client = analytics_module.octopus_client
    monkeypatch.setattr(client, "configured", lambda: False)

    async with SessionLocal() as db:
        tariff = await analytics_module.tariff_service.get_tariff(db)
        summary = await analytics_service.get_summary(db, HistoryRange.DAY)

    assert summary.import_kwh > 0
    assert summary.export_kwh > 0
    assert summary.breakdown is not None
    assert summary.breakdown.import_rate_gbp == pytest.approx(tariff.import_rate)
    night_rate = (
        tariff.night_import_rate if tariff.night_import_rate is not None else tariff.import_rate
    )
    assert summary.import_cost == pytest.approx(
        round(
            summary.breakdown.cheap_import_kwh * night_rate
            + summary.breakdown.peak_import_kwh * tariff.import_rate,
            2,
        )
    )
    assert summary.export_credit == pytest.approx(round(summary.export_kwh * tariff.export_rate, 2))
