"""Analytics queries — history series and energy summary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MetricSampleRow
from app.schemas.domain import (
    HistoryRange,
    LiveMetrics,
    MetricCompareDelta,
    MetricCompareResponse,
    MetricHistoryPoint,
    MetricHistoryResponse,
    MetricSummaryResponse,
)
from app.services.analytics_helpers import integrate_kwh, range_start, split_import_kwh
from app.services.data_source import apply_sample_source_filter
from app.services.octopus_client import octopus_client
from app.services.optimisation_score_service import compute_optimisation_score
from app.services.savings_calculation import SavingsInputs, compute_savings
from app.services.system_warnings_service import system_warnings_service
from app.services.tariff_service import tariff_service

_MAX_POINTS = {"day": 288, "week": 336, "month": 720, "year": 876}


def _range_start(range_name: HistoryRange) -> datetime:
    return range_start(range_name)


def _integrate_kwh(rows: list[MetricSampleRow], field: str) -> float:
    return integrate_kwh(rows, field)


def _split_import_kwh(
    rows: list[MetricSampleRow],
    off_peak_start: str,
    off_peak_end: str,
) -> tuple[float, float]:
    return split_import_kwh(rows, off_peak_start, off_peak_end)


def _compare_window_days(range_name: HistoryRange) -> int:
    if range_name == HistoryRange.DAY:
        return 1
    if range_name == HistoryRange.WEEK:
        return 7
    if range_name == HistoryRange.MONTH:
        return 30
    return 365


def _downsample(rows: list[MetricSampleRow], max_points: int) -> list[MetricSampleRow]:
    if len(rows) <= max_points:
        return rows
    step = len(rows) / max_points
    indices = [int(i * step) for i in range(max_points)]
    return [rows[i] for i in indices]


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

    cheap_import, peak_import = _split_import_kwh(
        rows, tariff.off_peak_start, tariff.off_peak_end
    )
    battery_charge = rows[-1].daily_battery_charge_kwh if rows else 0.0
    battery_discharge = rows[-1].daily_battery_discharge_kwh if rows else 0.0
    battery_charge = battery_charge or 0.0
    battery_discharge = battery_discharge or 0.0
    peak_avoided = min(battery_discharge, peak_import) if battery_discharge else 0.0

    result = compute_savings(
        SavingsInputs(
            consumption_kwh=consumption_kwh,
            import_kwh=import_kwh,
            export_kwh=export_kwh,
            pv_kwh=pv_kwh,
            cheap_import_kwh=cheap_import,
            peak_import_kwh=peak_import,
            battery_charge_kwh=battery_charge,
            battery_discharge_kwh=battery_discharge,
            peak_import_avoided_kwh=peak_avoided,
        ),
        tariff,
        import_rate_override=import_rate_override,
        export_rate_override=export_rate_override,
    )

    return MetricSummaryResponse(
        range=range_name,
        pv_kwh=round(pv_kwh, 3),
        consumption_kwh=round(consumption_kwh, 3),
        import_kwh=round(import_kwh, 3),
        export_kwh=round(export_kwh, 3),
        self_consumption_pct=round(min(100.0, self_consumption_pct), 1),
        import_cost=result.import_cost,
        export_credit=result.export_credit,
        net_cost=result.net_cost,
        estimated_cost_without_solar=result.estimated_without_solar,
        savings=result.savings,
        currency=tariff.currency,
        standing_charge=result.standing_charge,
        breakdown=result.breakdown,
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


async def enrich_day_summary_with_live(
    db: AsyncSession,
    summary: MetricSummaryResponse,
    metrics: LiveMetrics,
) -> MetricSummaryResponse:
    """Align day summary kWh totals with Sunsynk etoday fields from /metrics/live."""
    pv_kwh = metrics.daily_pv_kwh
    import_kwh = metrics.daily_import_kwh
    export_kwh = metrics.daily_export_kwh
    if pv_kwh <= 0 and import_kwh <= 0 and export_kwh <= 0:
        return summary

    self_consumed = max(0.0, pv_kwh - export_kwh)
    self_consumption_pct = (self_consumed / pv_kwh * 100.0) if pv_kwh > 0 else 0.0

    tariff = await tariff_service.get_tariff(db)
    import_rate_override, export_rate_override = await _octopus_rate_overrides()

    result = compute_savings(
        SavingsInputs(
            consumption_kwh=summary.consumption_kwh,
            import_kwh=import_kwh,
            export_kwh=export_kwh,
            pv_kwh=pv_kwh,
            battery_charge_kwh=metrics.daily_battery_charge_kwh or 0.0,
            battery_discharge_kwh=metrics.daily_battery_discharge_kwh or 0.0,
        ),
        tariff,
        import_rate_override=import_rate_override,
        export_rate_override=export_rate_override,
    )

    return summary.model_copy(
        update={
            "pv_kwh": round(pv_kwh, 3),
            "import_kwh": round(import_kwh, 3),
            "export_kwh": round(export_kwh, 3),
            "self_consumption_pct": round(min(100.0, self_consumption_pct), 1),
            "import_cost": result.import_cost,
            "export_credit": result.export_credit,
            "net_cost": result.net_cost,
            "estimated_cost_without_solar": result.estimated_without_solar,
            "savings": result.savings,
            "standing_charge": result.standing_charge,
            "breakdown": result.breakdown,
        }
    )


class AnalyticsService:
    async def get_history(
        self,
        db: AsyncSession,
        range_name: HistoryRange,
    ) -> MetricHistoryResponse:
        start = _range_start(range_name)
        result = await db.execute(
            apply_sample_source_filter(
                select(MetricSampleRow)
                .where(MetricSampleRow.timestamp >= start)
                .order_by(MetricSampleRow.timestamp.asc())
            )
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
                battery_power_w=row.battery_power_w,
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
            apply_sample_source_filter(
                select(MetricSampleRow)
                .where(MetricSampleRow.timestamp >= start)
                .order_by(MetricSampleRow.timestamp.asc())
            )
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

    async def get_enriched_summary(
        self,
        db: AsyncSession,
        range_name: HistoryRange,
    ) -> MetricSummaryResponse:
        summary = await self.get_summary(db, range_name)
        warnings_resp = await system_warnings_service.evaluate(db)
        score = compute_optimisation_score(
            import_kwh=summary.import_kwh,
            export_kwh=summary.export_kwh,
            pv_kwh=summary.pv_kwh,
            self_consumption_pct=summary.self_consumption_pct,
            breakdown=summary.breakdown,
            warnings=warnings_resp.warnings,
        )
        return summary.model_copy(
            update={
                "optimisation_score": score,
                "system_status": warnings_resp.status_headline,
            }
        )

    async def get_compare(
        self, db: AsyncSession, range_name: HistoryRange = HistoryRange.DAY
    ) -> MetricCompareResponse:
        now = datetime.now(timezone.utc)
        window_days = _compare_window_days(range_name)
        if range_name == HistoryRange.DAY:
            current_start = _range_start(HistoryRange.DAY)
            previous_start = current_start - timedelta(days=1)
        else:
            current_start = now - timedelta(days=window_days)
            previous_start = now - timedelta(days=window_days * 2)

        result = await db.execute(
            apply_sample_source_filter(
                select(MetricSampleRow)
                .where(MetricSampleRow.timestamp >= previous_start)
                .order_by(MetricSampleRow.timestamp.asc())
            )
        )
        all_rows = list(result.scalars().all())
        current_rows = [r for r in all_rows if _aware(r.timestamp) >= current_start]
        previous_rows = [
            r for r in all_rows if previous_start <= _aware(r.timestamp) < current_start
        ]

        import_rate_override, export_rate_override = await _octopus_rate_overrides()

        today = await _summary_from_rows(
            db,
            current_rows,
            range_name=range_name,
            import_rate_override=import_rate_override,
            export_rate_override=export_rate_override,
        )
        yesterday = await _summary_from_rows(
            db,
            previous_rows,
            range_name=range_name,
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
        return MetricCompareResponse(
            range=range_name,
            today=today,
            yesterday=yesterday,
            deltas=deltas,
        )


analytics_service = AnalyticsService()
