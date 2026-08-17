"""Finance reports aggregation for personal and business ledgers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.finance import (
    BusinessFinanceReport,
    CashflowHistoryPoint,
    FinanceReportsResponse,
    PersonalFinanceReport,
    PlHistoryPoint,
    ReportCategorySpend,
    ReportDebtLine,
    ReportExpenseLine,
)
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_budget_plan_service import finance_budget_plan_service
from app.services.finance.finance_calc import (
    accounts_from_schema,
    business_snapshot_view,
    company_position,
    compute_totals,
    directors_loan_sides,
    liabilities_from_schema,
    personal_net_worth,
    personal_snapshot_view,
    previous_month_key,
)
from app.services.finance.finance_ledger_service import finance_ledger_service
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service
from app.services.finance.finance_position_service import finance_position_service
from app.services.finance.quickfile_reports_service import quickfile_reports_service


def _debt_lines(liabilities: list[Any], *, scope: str) -> list[ReportDebtLine]:
    lines: list[ReportDebtLine] = []
    for debt in liabilities:
        if not getattr(debt, "is_active", True):
            continue
        debt_scope = getattr(getattr(debt, "scope", None), "value", getattr(debt, "scope", ""))
        if str(debt_scope) != scope:
            continue
        debt_type = getattr(
            getattr(debt, "debt_type", None),
            "value",
            getattr(debt, "debt_type", ""),
        )
        if debt_type == "directors_loan":
            continue
        lines.append(
            ReportDebtLine(
                id=int(debt.id),
                name=str(debt.name),
                debt_type=str(debt_type),
                balance_gbp=float(debt.balance_gbp),
                interest_rate_pct=float(debt.interest_rate_pct),
                minimum_payment_gbp=float(debt.minimum_payment_gbp),
                interest_rate_known=bool(getattr(debt, "interest_rate_known", True)),
            )
        )
    lines.sort(key=lambda item: item.balance_gbp, reverse=True)
    return lines


def _category_rows(rows: list[dict[str, Any]]) -> list[ReportCategorySpend]:
    return [
        ReportCategorySpend(
            category=str(row["category"]),
            amount_gbp=float(row["amount_gbp"]),
            transaction_count=int(row["transaction_count"]),
        )
        for row in rows
    ]


def _expense_rows(rows: list[dict[str, Any]]) -> list[ReportExpenseLine]:
    return [
        ReportExpenseLine(
            id=int(row["id"]),
            posted_on=str(row["posted_on"]),
            description=str(row["description"]),
            category=str(row["category"]),
            amount_gbp=float(row["amount_gbp"]),
            account_name=str(row.get("account_name") or ""),
        )
        for row in rows
    ]


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
        account_views = accounts_from_schema(accounts)
        liability_views = liabilities_from_schema(liabilities)
        totals = compute_totals(
            account_views,
            liability_views,
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

        personal_report = await self._build_personal_report(
            db,
            month=month,
            overview=overview,
            totals=totals,
            personal=personal,
            liabilities=liabilities,
            account_views=account_views,
            liability_views=liability_views,
        )
        business_report = await self._build_business_report(
            db,
            month=month,
            overview=overview,
            totals=totals,
            business=business,
            liabilities=liabilities,
            account_views=account_views,
            liability_views=liability_views,
            qf_reports=qf_reports,
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
            personal_report=personal_report,
            business_report=business_report,
        )

    async def _build_personal_report(
        self,
        db: AsyncSession,
        *,
        month: str,
        overview: Any,
        totals: Any,
        personal: Any,
        liabilities: list[Any],
        account_views: list[Any],
        liability_views: list[Any],
    ) -> PersonalFinanceReport:
        director_owes, company_owes = directors_loan_sides(account_views, liability_views)
        personal_bank = round(totals.personal_cash_gbp - totals.personal_overdraft_gbp, 2)
        net_worth = personal_net_worth(
            personal_bank=personal_bank,
            pension=totals.pension_gbp,
            personal_external_debt=totals.personal_debt_gbp,
            director_owes_company=director_owes,
            company_owes_director=company_owes,
        )
        tx = await finance_ledger_service.month_flow_totals(db, month, scope="personal")
        categories = await finance_ledger_service.spending_by_category(
            db, month, scope="personal"
        )
        expenses = await finance_ledger_service.largest_expenses(db, month, scope="personal")

        income = spending = surplus = None
        household = repayments = None
        flow_source = "none"
        flow_note = "No personal snapshot or imported transactions for this month."
        if personal is not None and (
            personal.monthly_income_gbp > 0 or personal.monthly_spending_gbp > 0
        ):
            income = round(personal.monthly_income_gbp, 2)
            spending = round(personal.monthly_spending_gbp, 2)
            surplus = round(personal.surplus_deficit_gbp, 2)
            household = round(personal.household_bills_gbp, 2)
            repayments = round(personal.debt_repayments_gbp, 2)
            flow_source = "snapshot"
            flow_note = "From the saved personal snapshot for this month."
        elif tx["transaction_count"] > 0:
            income = tx["income_gbp"]
            spending = tx["spending_gbp"]
            surplus = tx["net_gbp"]
            flow_source = "transactions"
            flow_note = "From imported personal transactions (transfers excluded)."
        elif overview.monthly_flow_source == "budget" and (
            overview.monthly_income_gbp > 0 or overview.monthly_spending_gbp > 0
        ):
            income = round(overview.monthly_income_gbp, 2)
            spending = round(overview.monthly_spending_gbp, 2)
            surplus = round(overview.monthly_surplus_gbp, 2)
            flow_source = "budget"
            flow_note = "From the active budget plan — not imported transactions."

        prev_key = previous_month_key(month)
        prev_snap = await finance_overview_service.personal_snapshot_for_month(db, prev_key)
        prev_income = prev_spending = None
        income_change = spending_change = None
        if prev_snap is not None and (
            prev_snap.monthly_income_gbp > 0 or prev_snap.monthly_spending_gbp > 0
        ):
            prev_income = round(prev_snap.monthly_income_gbp, 2)
            prev_spending = round(prev_snap.monthly_spending_gbp, 2)
        else:
            prev_tx = await finance_ledger_service.month_flow_totals(
                db, prev_key, scope="personal"
            )
            if prev_tx["transaction_count"] > 0:
                prev_income = prev_tx["income_gbp"]
                prev_spending = prev_tx["spending_gbp"]
        if income is not None and prev_income is not None:
            income_change = round(income - prev_income, 2)
        if spending is not None and prev_spending is not None:
            spending_change = round(spending - prev_spending, 2)

        empty = None
        if flow_source == "none" and tx["transaction_count"] == 0:
            empty = (
                "No personal snapshot or imported transactions for this month. "
                "Save a snapshot on Personal, or import a statement."
            )

        return PersonalFinanceReport(
            month=month,
            cash_gbp=personal_bank,
            overdraft_gbp=totals.personal_overdraft_gbp,
            debt_gbp=totals.personal_debt_gbp,
            pension_gbp=totals.pension_gbp,
            property_gbp=totals.property_gbp,
            net_worth_gbp=net_worth,
            income_gbp=income,
            spending_gbp=spending,
            surplus_gbp=surplus,
            household_bills_gbp=household,
            debt_repayments_gbp=repayments,
            flow_source=flow_source,
            flow_note=flow_note,
            transaction_count=int(tx["transaction_count"]),
            spending_by_category=_category_rows(categories),
            largest_expenses=_expense_rows(expenses),
            debts=_debt_lines(liabilities, scope="personal"),
            previous_month_income_gbp=prev_income,
            previous_month_spending_gbp=prev_spending,
            income_change_gbp=income_change,
            spending_change_gbp=spending_change,
            empty_state=empty,
        )

    async def _build_business_report(
        self,
        db: AsyncSession,
        *,
        month: str,
        overview: Any,
        totals: Any,
        business: Any,
        liabilities: list[Any],
        account_views: list[Any],
        liability_views: list[Any],
        qf_reports: Any,
    ) -> BusinessFinanceReport:
        director_owes, company_owes = directors_loan_sides(account_views, liability_views)
        business_bank = round(totals.business_cash_gbp - totals.business_overdraft_gbp, 2)
        position = company_position(
            business_bank=business_bank,
            debtors=totals.debtors_gbp,
            vat_reserve=totals.vat_reserve_gbp,
            corp_tax_reserve=totals.corp_tax_reserve_gbp,
            business_external_debt=totals.business_debt_gbp,
            director_owes_company=director_owes,
            company_owes_director=company_owes,
        )
        tx = await finance_ledger_service.month_flow_totals(db, month, scope="business")
        categories = await finance_ledger_service.spending_by_category(
            db, month, scope="business"
        )
        expenses_rows = await finance_ledger_service.largest_expenses(
            db, month, scope="business"
        )

        turnover = expenses = profit = None
        pl_source = "none"
        pl_note = "No business snapshot or QuickFile P&L for this month."
        ytd_turnover = ytd_expenses = ytd_profit = vat_liability = None

        qf_month = getattr(qf_reports, "profit_and_loss_month", None) if qf_reports else None
        qf_ytd = getattr(qf_reports, "profit_and_loss_ytd", None) if qf_reports else None
        qf_bs = getattr(qf_reports, "balance_sheet", None) if qf_reports else None
        if qf_month is not None and (qf_month.turnover_gbp > 0 or qf_month.expenses_gbp > 0):
            turnover = round(qf_month.turnover_gbp, 2)
            expenses = round(qf_month.expenses_gbp, 2)
            profit = round(qf_month.net_profit_gbp, 2)
            pl_source = "quickfile"
            pl_note = "From the last synced QuickFile profit and loss."
        elif business is not None and (business.turnover_gbp > 0 or business.expenses_gbp > 0):
            turnover = round(business.turnover_gbp, 2)
            expenses = round(business.expenses_gbp, 2)
            profit = round(
                business.profit_estimate_gbp
                or (business.turnover_gbp - business.expenses_gbp),
                2,
            )
            pl_source = "snapshot"
            pl_note = "From the saved business snapshot for this month."
        elif tx["transaction_count"] > 0:
            turnover = tx["income_gbp"]
            expenses = tx["spending_gbp"]
            profit = tx["net_gbp"]
            pl_source = "transactions"
            pl_note = "From imported business transactions (transfers excluded)."

        if qf_ytd is not None and (qf_ytd.turnover_gbp > 0 or qf_ytd.expenses_gbp > 0):
            ytd_turnover = round(qf_ytd.turnover_gbp, 2)
            ytd_expenses = round(qf_ytd.expenses_gbp, 2)
            ytd_profit = round(qf_ytd.net_profit_gbp, 2)
        if qf_bs is not None and getattr(qf_bs, "vat_liability_gbp", 0):
            vat_liability = round(float(qf_bs.vat_liability_gbp), 2)

        empty = None
        if pl_source == "none" and tx["transaction_count"] == 0 and business_bank == 0:
            empty = (
                "No company P&L, snapshot, or imported business transactions yet. "
                "Sync QuickFile on Connect banks, or save a business snapshot."
            )

        return BusinessFinanceReport(
            month=month,
            cash_gbp=business_bank,
            overdraft_gbp=totals.business_overdraft_gbp,
            debt_gbp=totals.business_debt_gbp,
            debtors_gbp=totals.debtors_gbp,
            creditors_gbp=totals.creditors_gbp,
            vat_reserve_gbp=totals.vat_reserve_gbp,
            corp_tax_reserve_gbp=totals.corp_tax_reserve_gbp,
            directors_loan_gbp=totals.directors_loan_gbp,
            company_owes_director_gbp=company_owes,
            director_owes_company_gbp=director_owes,
            company_position_gbp=position,
            turnover_gbp=turnover,
            expenses_gbp=expenses,
            profit_gbp=profit,
            ytd_turnover_gbp=ytd_turnover,
            ytd_expenses_gbp=ytd_expenses,
            ytd_profit_gbp=ytd_profit,
            vat_liability_gbp=vat_liability,
            pl_source=pl_source,
            pl_note=pl_note,
            transaction_count=int(tx["transaction_count"]),
            spending_by_category=_category_rows(categories),
            largest_expenses=_expense_rows(expenses_rows),
            debts=_debt_lines(liabilities, scope="business"),
            empty_state=empty,
        )


finance_reports_service = FinanceReportsService()
