"""Finance reports aggregation."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailySavingsRow, EnergyDailySnapshotRow
from app.schemas.finance import FinanceReportsResponse
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service


class FinanceReportsService:
    async def get_reports(
        self, db: AsyncSession, month: str | None = None
    ) -> FinanceReportsResponse:
        if month is None:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        overview = await finance_overview_service.get_overview(db)
        personal = await finance_overview_service.latest_personal_snapshot(db)
        business = await finance_overview_service.latest_business_snapshot(db)
        liabilities = await finance_liabilities_service.list_liabilities(db)
        total_debt = finance_liabilities_service.total_debt(liabilities)

        savings_rows = await db.scalars(
            select(DailySavingsRow).where(DailySavingsRow.date.startswith(month))
        )
        energy_savings = sum(r.estimated_saving_gbp for r in savings_rows.all())

        energy_snap = await db.scalars(
            select(EnergyDailySnapshotRow).where(EnergyDailySnapshotRow.date.startswith(month))
        )
        energy_snap_list = list(energy_snap.all())
        vs_forecast = "On track"
        if energy_snap_list:
            avg = sum(s.savings_gbp for s in energy_snap_list) / len(energy_snap_list)
            if avg < 1.0:
                vs_forecast = "Below forecast"

        return FinanceReportsResponse(
            month=month,
            personal_snapshot=personal,
            business_snapshot=business,
            net_worth_gbp=overview.net_worth_estimate_gbp,
            total_debt_gbp=total_debt,
            debt_reduction_gbp=0.0,
            energy_savings_gbp=round(energy_savings, 2),
            energy_savings_vs_forecast=vs_forecast,
        )


finance_reports_service = FinanceReportsService()
