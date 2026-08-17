"""Persisted daily savings rollup and history queries."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailySavingsRow, EnergyDailySnapshotRow, MetricSampleRow
from app.schemas.domain import (
    DailySavingsPoint,
    HistoryRange,
    SavingsHistoryResponse,
)
from app.services.analytics_service import analytics_service
from app.services.system_warnings_service import system_warnings_service
from app.services.tariff_clock import tariff_now


class DailySavingsService:
    async def upsert_today(self, db: AsyncSession) -> DailySavingsRow | None:
        from app.schemas.domain import HistoryRange

        today = tariff_now().strftime("%Y-%m-%d")
        summary = await analytics_service.get_enriched_summary(db, HistoryRange.DAY)
        warnings = await system_warnings_service.evaluate(db)
        now = datetime.now(timezone.utc)

        row = await db.scalar(
            select(DailySavingsRow).where(DailySavingsRow.date == today)
        )
        warnings_json = json.dumps([w.model_dump() for w in warnings.warnings])
        score = summary.optimisation_score.total if summary.optimisation_score else 0

        payload = {
            "solar_kwh": summary.pv_kwh,
            "house_kwh": summary.consumption_kwh,
            "import_kwh": summary.import_kwh,
            "export_kwh": summary.export_kwh,
            "battery_charge_kwh": (
                summary.breakdown.battery_charge_kwh if summary.breakdown else 0.0
            ),
            "battery_discharge_kwh": (
                summary.breakdown.battery_discharge_kwh if summary.breakdown else 0.0
            ),
            "actual_cost_gbp": summary.net_cost,
            "estimated_no_solar_cost_gbp": summary.estimated_cost_without_solar,
            "estimated_saving_gbp": summary.savings,
            "export_credit_gbp": summary.export_credit,
            "standing_charge_gbp": summary.standing_charge,
            "optimisation_score": score,
            "warnings_json": warnings_json,
            "updated_at": now,
        }

        if row is None:
            row = DailySavingsRow(date=today, created_at=now, **payload)
            db.add(row)
        else:
            for key, value in payload.items():
                setattr(row, key, value)
        await db.commit()
        await db.refresh(row)
        await self._upsert_energy_snapshot(db, today, summary, warnings_json)
        return row

    async def _upsert_energy_snapshot(
        self,
        db: AsyncSession,
        today: str,
        summary,
        warnings_json: str,
    ) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        warnings = json.loads(warnings_json or "[]")
        peak_discharge_ok = True
        for w in warnings:
            text = (
                f"{w.get('title', '')} {w.get('message', '')}"
                if isinstance(w, dict)
                else str(w)
            )
            if "discharg" in text.lower() or "peak" in text.lower():
                peak_discharge_ok = False
                break

        day_start = tariff_now().replace(hour=0, minute=0, second=0, microsecond=0)
        samples = await db.scalars(
            select(MetricSampleRow).where(MetricSampleRow.timestamp >= day_start)
        )
        sample_list = list(samples.all())
        avg_soc = (
            sum(s.battery_soc_pct for s in sample_list) / len(sample_list)
            if sample_list
            else 0.0
        )

        payload = {
            "pv_kwh": summary.pv_kwh,
            "import_kwh": summary.import_kwh,
            "export_kwh": summary.export_kwh,
            "battery_charge_kwh": (
                summary.breakdown.battery_charge_kwh if summary.breakdown else 0.0
            ),
            "battery_discharge_kwh": (
                summary.breakdown.battery_discharge_kwh if summary.breakdown else 0.0
            ),
            "avg_soc_pct": round(avg_soc, 1),
            "savings_gbp": summary.savings,
            "export_credit_gbp": summary.export_credit,
            "peak_discharge_ok": peak_discharge_ok,
            "alerts_json": warnings_json,
        }

        snap = await db.scalar(
            select(EnergyDailySnapshotRow).where(EnergyDailySnapshotRow.date == today)
        )
        if snap is None:
            db.add(EnergyDailySnapshotRow(date=today, created_at=now, **payload))
        else:
            for key, value in payload.items():
                setattr(snap, key, value)
        await db.commit()

    async def get_history(
        self, db: AsyncSession, range_name: HistoryRange
    ) -> SavingsHistoryResponse:
        now = tariff_now()
        if range_name == HistoryRange.WEEK:
            start_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        elif range_name == HistoryRange.MONTH:
            start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        elif range_name == HistoryRange.YEAR:
            start_date = (now - timedelta(days=365)).strftime("%Y-%m-%d")
        else:
            start_date = now.strftime("%Y-%m-%d")

        rows = await db.scalars(
            select(DailySavingsRow)
            .where(DailySavingsRow.date >= start_date)
            .order_by(DailySavingsRow.date.asc())
        )
        points = [
            DailySavingsPoint(
                date=r.date,
                savings_gbp=r.estimated_saving_gbp,
                net_cost_gbp=r.actual_cost_gbp,
                estimated_no_solar_gbp=r.estimated_no_solar_cost_gbp,
                optimisation_score=r.optimisation_score,
                pv_kwh=r.solar_kwh,
                import_kwh=r.import_kwh,
            )
            for r in rows.all()
        ]
        total = sum(p.savings_gbp for p in points)
        ytd_start = now.replace(month=1, day=1).strftime("%Y-%m-%d")
        ytd = sum(p.savings_gbp for p in points if p.date >= ytd_start)
        days_elapsed = max(1, now.timetuple().tm_yday)
        projected = (ytd / days_elapsed) * 365 if ytd > 0 else total * (365 / max(len(points), 1))

        return SavingsHistoryResponse(
            range=range_name,
            points=points,
            total_savings_gbp=round(total, 2),
            projected_annual_gbp=round(projected, 2),
            year_to_date_gbp=round(ytd, 2),
        )


daily_savings_service = DailySavingsService()
