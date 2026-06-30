"""Analytics queries — history series and energy summary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MetricSampleRow
from app.schemas.domain import (
    HistoryRange,
    MetricCompareDelta,
    MetricCompareResponse,
    MetricHistoryPoint,
    MetricHistoryResponse,
    MetricSummaryResponse,
)
from app.services.octopus_client import octopus_client
from app.services.tariff_service import tariff_service

_MAX_POINTS = {"day": 288, "week": 336, "month": 720}


def _range_start(range_name: HistoryRange) -> datetime:
    now = datetime.now(timezone.utc)
    if range_name == HistoryRange.DAY:
        return now - timedelta(days=1)
    if range_name == HistoryRange.WEEK:
        return now - timedelta(days=7)
    return now - timedelta(days=30)


def _downsample(rows: list[MetricSampleRow], max_points: int) -> list[MetricSampleRow]:
    if len(rows) <= max_points:
        return rows
    step = len(rows) / max_points
    indices = [int(i * step) for i in range(max_points)]
    return [rows[i] for i in indices]


def _integrate_kwh(rows: list[MetricSampleRow], field: str) -> float:
    if len(rows) < 2:
        return 0.0
    total_wh = 0.0
    for prev, curr in zip(rows, rows[1:]):
        dt_hours = (curr.timestamp - prev.timestamp).total_seconds() / 3600.0
        if dt_hours <= 0:
            continue
        p1 = getattr(prev, field)
        p2 = getattr(curr, field)
        total_wh += (p1 + p2) / 2.0 * dt_hours
    return total_wh / 1000.0


async def _summary_from_rows(
    db: AsyncSession,
    rows: list[MetricSampleRow],
    *,
    range_name: HistoryRange,
    import_rate_override: float | None = None,
    export_rate_override: float | None = None,
) -> MetricSummaryResponse:
    pv_kwh = _integrate_kwh(rows, "pv_power_w")
    consumption_kwh = _integrate_kwh(rows, "house_load_w")
    import_kwh = _integrate_kwh(rows, "grid_import_w")
    export_kwh = _integrate_kwh(rows, "grid_export_w")

    self_consumed = max(0.0, pv_kwh - export_kwh)
    self_consumption_pct = (self_consumed / pv_kwh * 100.0) if pv_kwh > 0 else 0.0

    tariff = await tariff_service.get_tariff(db)
    import_rate = import_rate_override if import_rate_override is not None else tariff.import_rate
    export_rate = export_rate_override if export_rate_override is not None else tariff.export_rate

    import_cost = import_kwh * import_rate
    export_credit = export_kwh * export_rate
    net_cost = import_cost - export_credit
    estimated_without_solar = consumption_kwh * import_rate
    savings = estimated_without_solar - net_cost

    return MetricSummaryResponse(
        range=range_name,
        pv_kwh=round(pv_kwh, 3),
        consumption_kwh=round(consumption_kwh, 3),
        import_kwh=round(import_kwh, 3),
        export_kwh=round(export_kwh, 3),
        self_consumption_pct=round(min(100.0, self_consumption_pct), 1),
        import_cost=round(import_cost, 2),
        export_credit=round(export_credit, 2),
        net_cost=round(net_cost, 2),
        estimated_cost_without_solar=round(estimated_without_solar, 2),
        savings=round(savings, 2),
        currency=tariff.currency,
    )


def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


async def _octopus_rate_overrides() -> tuple[float | None, float | None]:
    if not octopus_client.configured():
        return None, None
    try:
        import_rate = await octopus_client.get_import_rate_gbp()
        export_rate = await octopus_client.get_export_rate_gbp()
        return import_rate, export_rate
    except Exception:
        return None, None


class AnalyticsService:
    async def get_history(
        self,
        db: AsyncSession,
        range_name: HistoryRange,
    ) -> MetricHistoryResponse:
        start = _range_start(range_name)
        result = await db.execute(
            select(MetricSampleRow)
            .where(MetricSampleRow.timestamp >= start)
            .order_by(MetricSampleRow.timestamp.asc())
        )
        rows = list(result.scalars().all())
        rows = _downsample(rows, _MAX_POINTS[range_name.value])
        points = [
            MetricHistoryPoint(
                timestamp=row.timestamp,
                pv_power_w=row.pv_power_w,
                battery_soc_pct=row.battery_soc_pct,
                house_load_w=row.house_load_w,
                grid_import_w=row.grid_import_w,
                grid_export_w=row.grid_export_w,
                battery_soh_pct=row.battery_soh_pct,
            )
            for row in rows
        ]
        return MetricHistoryResponse(range=range_name, points=points)

    async def get_summary(
        self,
        db: AsyncSession,
        range_name: HistoryRange,
    ) -> MetricSummaryResponse:
        start = _range_start(range_name)
        result = await db.execute(
            select(MetricSampleRow)
            .where(MetricSampleRow.timestamp >= start)
            .order_by(MetricSampleRow.timestamp.asc())
        )
        rows = list(result.scalars().all())

        import_rate_override, export_rate_override = await _octopus_rate_overrides()

        return await _summary_from_rows(
            db,
            rows,
            range_name=range_name,
            import_rate_override=import_rate_override,
            export_rate_override=export_rate_override,
        )

    async def get_compare(self, db: AsyncSession) -> MetricCompareResponse:
        now = datetime.now(timezone.utc)
        today_start = now - timedelta(days=1)
        yesterday_start = now - timedelta(days=2)

        result = await db.execute(
            select(MetricSampleRow)
            .where(MetricSampleRow.timestamp >= yesterday_start)
            .order_by(MetricSampleRow.timestamp.asc())
        )
        all_rows = list(result.scalars().all())
        today_rows = [r for r in all_rows if _aware(r.timestamp) >= today_start]
        yesterday_rows = [
            r for r in all_rows if yesterday_start <= _aware(r.timestamp) < today_start
        ]

        import_rate_override, export_rate_override = await _octopus_rate_overrides()

        today = await _summary_from_rows(
            db,
            today_rows,
            range_name=HistoryRange.DAY,
            import_rate_override=import_rate_override,
            export_rate_override=export_rate_override,
        )
        yesterday = await _summary_from_rows(
            db,
            yesterday_rows,
            range_name=HistoryRange.DAY,
            import_rate_override=import_rate_override,
            export_rate_override=export_rate_override,
        )

        deltas = [
            MetricCompareDelta(
                label="Savings",
                today=today.savings,
                yesterday=yesterday.savings,
                unit=today.currency,
                higher_is_better=True,
            ),
            MetricCompareDelta(
                label="PV generated",
                today=today.pv_kwh,
                yesterday=yesterday.pv_kwh,
                unit="kWh",
                higher_is_better=True,
            ),
            MetricCompareDelta(
                label="Grid import",
                today=today.import_kwh,
                yesterday=yesterday.import_kwh,
                unit="kWh",
                higher_is_better=False,
            ),
            MetricCompareDelta(
                label="Self-consumed",
                today=today.self_consumption_pct,
                yesterday=yesterday.self_consumption_pct,
                unit="%",
                higher_is_better=True,
            ),
        ]
        return MetricCompareResponse(today=today, yesterday=yesterday, deltas=deltas)


analytics_service = AnalyticsService()
