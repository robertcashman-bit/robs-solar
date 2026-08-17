"""Finance reports aggregation."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.finance import CashflowHistoryPoint, FinanceReportsResponse, PlHistoryPoint
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_budget_plan_service import finance_budget_plan_service
from app.services.finance.finance_calc import (
    accounts_from_schema,
    business_snapshot_view,
    compute_totals,
    liabilities_from_schema,
    personal_snapshot_view,
)
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service
from app.services.finance.finance_position_service import finance_position_service
from app.services.finance.quickfile_reports_service import quickfile_reports_service


class FinanceReportsService:
    async def get_reports(
        self, db: AsyncSession, month: str | None = None
    ) -> FinanceReportsResponse:
        if month is None:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        overview = await finance_overview_service.get_overview(
            db, month=month, refresh_live=False
        )
        personal = await finance_overview_service.personal_snapshot_for_month(db, month)
        business = await finance_overview_service.business_snapshot_for_month(db, month)
        accounts = await finance_accounts_service.list_accounts(db, refresh_live=False)
        liabilities = await finance_liabilities_service.list_liabilities(
            db, sync_accounts=False
        )
        totals = compute_totals(
            accounts_from_schema(accounts),
            liabilities_from_schema(liabilities),
            personal_snapshot_view(personal),
            business_snapshot_view(business),
        )

        has_original_balances = any(
            getattr(debt, "original_balance_gbp", None) is not None for debt in liabilities
        )
        month_has_history = personal is not None or business is not None
        stored = await finance_position_service.get_for_month(db, month)
        prior = await finance_position_service.get_latest_before(db, month)
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        if month == current_month:
            total_debt = overview.total_debt_gbp
            net_worth = overview.net_worth_estimate_gbp
        elif stored is not None:
            total_debt = stored.total_debt_gbp
            net_worth = stored.net_worth_gbp
        else:
            # A past month with no recorded position must not inherit today's
            # live balances. That invented a fake reduction against older rows.
            total_debt = None
            net_worth = None
        debt_reduction = None
        debt_reduction_available = False
        previous_debt = None
        if stored is not None and prior is not None and total_debt is not None:
            debt_reduction = round(prior.total_debt_gbp - total_debt, 2)
            debt_reduction_available = True
            previous_debt = prior.total_debt_gbp
        elif month == current_month and month_has_history and has_original_balances:
            debt_reduction = totals.debt_reduction_gbp
        snapshots = await finance_overview_service.list_personal_snapshots(db, limit=24)
        cashflow_by_month: dict[str, CashflowHistoryPoint] = {}
        for snap in reversed(snapshots):
            key = snap.snapshot_date[:7]
            cashflow_by_month[key] = CashflowHistoryPoint(
                month=key,
                income_gbp=snap.monthly_income_gbp,
                spending_gbp=snap.monthly_spending_gbp,
                surplus_gbp=snap.surplus_deficit_gbp,
            )
        history = await finance_position_service.list_history(db)
        qf_reports = await quickfile_reports_service.get_stored_reports(db)
        business_snaps = await finance_overview_service.list_business_snapshots(db, limit=24)
        pl_by_month: dict[str, PlHistoryPoint] = {}
        for snap in reversed(business_snaps):
            key = snap.snapshot_date[:7]
            profit = snap.profit_estimate_gbp or (snap.turnover_gbp - snap.expenses_gbp)
            pl_by_month[key] = PlHistoryPoint(
                month=key,
                turnover_gbp=snap.turnover_gbp,
                expenses_gbp=snap.expenses_gbp,
                profit_gbp=profit,
            )
        return FinanceReportsResponse(
            month=month,
            personal_snapshot=personal,
            business_snapshot=business,
            net_worth_gbp=net_worth,
            total_debt_gbp=total_debt,
            debt_reduction_gbp=debt_reduction,
            energy_savings_gbp=0,
            energy_savings_vs_forecast="",
            debt_reduction_available=debt_reduction_available,
            previous_month_debt_gbp=previous_debt,
            cashflow_history=list(cashflow_by_month.values()),
            debt_history=finance_position_service.as_debt_history(history),
            pl_history=list(pl_by_month.values()),
            quickfile_reports=qf_reports,
            active_budget=await finance_budget_plan_service.get_active_summary(db),
            budget_vs_actual=await finance_budget_plan_service.vs_actual(db, month),
        )


finance_reports_service = FinanceReportsService()
