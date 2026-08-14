"""Finance reports aggregation."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BusinessFinanceSnapshotRow, DailySavingsRow, EnergyDailySnapshotRow
from app.schemas.finance import FinanceReportsResponse, PlHistoryPoint, PlHistoryResponse
from app.services.energy_activity import row_has_energy_activity
from app.services.finance.finance_overview_service import finance_overview_service
from app.services.finance.quickfile_reports_service import quickfile_reports_service


class FinanceReportsService:
    async def get_reports(
        self, db: AsyncSession, month: str | None = None
    ) -> FinanceReportsResponse:
        if month is None:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        overview = await finance_overview_service.get_overview(db)
        personal = await finance_overview_service.latest_personal_snapshot(db)
        business = await finance_overview_service.business_snapshot_for_month(db, month)
        if business is None:
            business = await finance_overview_service.latest_business_snapshot(db)
        # Use the same authoritative total as Overview (accounts + personal liabilities).
        total_debt = overview.total_debt_gbp

        savings_rows = [
            row
            for row in (
                await db.scalars(
                    select(DailySavingsRow).where(DailySavingsRow.date.startswith(month))
                )
            ).all()
            if row_has_energy_activity(row)
        ]
        energy_savings = sum(r.estimated_saving_gbp for r in savings_rows)

        energy_snap_list = [
            snap
            for snap in (
                await db.scalars(
                    select(EnergyDailySnapshotRow).where(
                        EnergyDailySnapshotRow.date.startswith(month)
                    )
                )
            ).all()
            if row_has_energy_activity(snap)
        ]
        vs_forecast = "On track"
        if not savings_rows and not energy_snap_list:
            vs_forecast = "Energy data unavailable"
        elif energy_snap_list:
            avg = sum(s.savings_gbp for s in energy_snap_list) / len(energy_snap_list)
            if avg < 1.0:
                vs_forecast = "Below forecast"

        qf_reports = await quickfile_reports_service.get_stored_reports(db)

        from app.services.finance.finance_budget_plan_service import (
            finance_budget_plan_service,
        )

        active_budget = await finance_budget_plan_service.get_active_summary(db)
        budget_vs_actual = await finance_budget_plan_service.variance_for_active(
            db, month=month
        )

        return FinanceReportsResponse(
            month=month,
            personal_snapshot=personal,
            business_snapshot=business,
            quickfile_reports=qf_reports,
            net_worth_gbp=overview.net_worth_estimate_gbp,
            total_debt_gbp=total_debt,
            debt_reduction_gbp=0.0,
            energy_savings_gbp=round(energy_savings, 2),
            energy_savings_vs_forecast=vs_forecast,
            budget_vs_actual=budget_vs_actual,
            active_budget=active_budget,
        )

    async def get_pl_history(self, db: AsyncSession, *, months: int = 12) -> PlHistoryResponse:
        rows = list(
            (
                await db.scalars(
                    select(BusinessFinanceSnapshotRow).order_by(
                        BusinessFinanceSnapshotRow.snapshot_date.desc()
                    )
                )
            ).all()
        )
        by_month: dict[str, BusinessFinanceSnapshotRow] = {}
        for row in rows:
            key = row.snapshot_date[:7]
            if key not in by_month:
                by_month[key] = row
        points = [
            PlHistoryPoint(
                month=month,
                turnover_gbp=round(row.turnover_gbp, 2),
                expenses_gbp=round(row.expenses_gbp, 2),
                profit_gbp=round(row.profit_estimate_gbp, 2),
            )
            for month, row in sorted(by_month.items())
        ]
        if months > 0:
            points = points[-months:]
        return PlHistoryResponse(points=points)


finance_reports_service = FinanceReportsService()
