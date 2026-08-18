"""Aggregated finance overview dashboard."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BusinessFinanceSnapshotRow, PersonalFinanceSnapshotRow
from app.schemas.finance import (
    BusinessFinanceSnapshot,
    BusinessFinanceSnapshotCreate,
    FinanceOverviewResponse,
    PersonalFinanceSnapshot,
    PersonalFinanceSnapshotCreate,
)
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_calc import (
    MonthlyFlow,
    accounts_from_schema,
    business_snapshot_view,
    company_position,
    compute_totals,
    directors_loan_sides,
    external_debt_gbp,
    high_interest_debt_gbp,
    instrument_configured,
    liabilities_from_schema,
    monthly_interest_from_debts,
    personal_net_worth,
    personal_snapshot_view,
    pick_open_banking_flow,
    resolve_monthly_flow,
    upcoming_payments,
)
from app.services.finance.finance_insights_service import finance_insights_service
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.snapshot_dates import normalize_snapshot_date


def _matches_month(column, month: str):
    key = month.strip()
    return or_(column == key, column.startswith(key))


def _personal_snapshot_order():
    return (
        PersonalFinanceSnapshotRow.snapshot_date.desc(),
        PersonalFinanceSnapshotRow.created_at.desc(),
        PersonalFinanceSnapshotRow.id.desc(),
    )


def _business_snapshot_order():
    return (
        BusinessFinanceSnapshotRow.snapshot_date.desc(),
        BusinessFinanceSnapshotRow.created_at.desc(),
        BusinessFinanceSnapshotRow.id.desc(),
    )


def _safe_json(raw: str | None) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _personal_from_row(row: PersonalFinanceSnapshotRow) -> PersonalFinanceSnapshot:
    return PersonalFinanceSnapshot(
        id=row.id,
        snapshot_date=row.snapshot_date,
        monthly_income_gbp=row.monthly_income_gbp,
        monthly_spending_gbp=row.monthly_spending_gbp,
        household_bills_gbp=row.household_bills_gbp,
        debt_repayments_gbp=row.debt_repayments_gbp,
        surplus_deficit_gbp=row.surplus_deficit_gbp,
        notes=row.notes,
        breakdown=_safe_json(row.breakdown_json),
        created_at=row.created_at,
    )


def _business_from_row(row: BusinessFinanceSnapshotRow) -> BusinessFinanceSnapshot:
    profit = row.turnover_gbp - row.expenses_gbp
    return BusinessFinanceSnapshot(
        id=row.id,
        snapshot_date=row.snapshot_date,
        turnover_gbp=row.turnover_gbp,
        expenses_gbp=row.expenses_gbp,
        vat_reserve_gbp=row.vat_reserve_gbp,
        corp_tax_reserve_gbp=row.corp_tax_reserve_gbp,
        debtors_gbp=row.debtors_gbp,
        creditors_gbp=row.creditors_gbp,
        profit_estimate_gbp=row.profit_estimate_gbp or profit,
        cash_available_to_draw_gbp=row.cash_available_to_draw_gbp,
        notes=row.notes,
        breakdown=_safe_json(row.breakdown_json),
        created_at=row.created_at,
    )


class FinanceOverviewService:
    async def get_overview(
        self,
        db: AsyncSession,
        month: str | None = None,
        *,
        refresh_live: bool = False,
        fresh: bool = False,
        personal_period: str = "1m",
        business_period: str = "1m",
    ) -> FinanceOverviewResponse:
        started = time.perf_counter()
        if month is None:
            month = datetime.now(timezone.utc).strftime("%Y-%m")

        from app.services.finance.finance_overview_cache_service import (
            finance_overview_cache_service,
        )
        from app.services.finance.finance_period import parse_period

        personal_period = parse_period(personal_period)
        business_period = parse_period(business_period)

        # Login / first paint must never wait on QuickFile or Lunch Flow.
        if refresh_live:
            from app.services.finance.finance_live_refresh_service import (
                finance_live_refresh_service,
            )

            await finance_live_refresh_service.ensure_fresh(db)
            await finance_overview_cache_service.clear(db, month)

        overview = None
        if not refresh_live and not fresh:
            fingerprint = await finance_overview_cache_service.fingerprint(db)
            cached = await finance_overview_cache_service.read(
                db, month, current_fingerprint=fingerprint
            )
            if cached is not None:
                overview = cached

        if overview is None:
            overview = await self._compute_overview(db, month, refresh_live=refresh_live)
            fingerprint = await finance_overview_cache_service.fingerprint(db)
            # Cache base snapshot figures without period overlays so lookback
            # choices never poison the shared month cache.
            overview.personal_period_flow = None
            overview.business_period_flow = None
            await finance_overview_cache_service.write(db, month, overview, fingerprint)

        await self._attach_period_flows(
            db,
            overview,
            personal_period=personal_period,
            business_period=business_period,
        )
        overview.compute_ms = round((time.perf_counter() - started) * 1000, 1)
        return overview

    async def _compute_overview(
        self,
        db: AsyncSession,
        month: str,
        *,
        refresh_live: bool,
    ) -> FinanceOverviewResponse:
        accounts = await finance_accounts_service.list_accounts(
            db, refresh_live=False
        )
        if refresh_live:
            await finance_liabilities_service.ensure_from_accounts(db)
        liabilities = await finance_liabilities_service.list_liabilities(
            db, sync_accounts=False
        )
        personal_snap = await self.personal_snapshot_for_month(db, month)
        business_snap = await self.business_snapshot_for_month(db, month)
        account_views = accounts_from_schema(accounts)
        liability_views = liabilities_from_schema(liabilities)
        totals = compute_totals(
            account_views,
            liability_views,
            personal_snapshot_view(personal_snap),
            business_snapshot_view(business_snap),
        )
        open_banking = await self._open_banking_flow(db)
        cashflow_income = cashflow_spending = cashflow_bills = 0.0
        try:
            from app.services.finance.finance_cashflow_service import finance_cashflow_service

            cashflow_income, cashflow_spending, cashflow_bills = (
                await finance_cashflow_service.month_flow(db, month)
            )
        except Exception:
            pass
        budgeted = actual = 0.0
        budget_income = budget_spending = 0.0
        try:
            from app.services.finance.finance_budget_service import finance_budget_service

            budgeted, actual = await finance_budget_service.month_totals(db, month)
            budget_spending = actual if actual > 0 else budgeted
        except Exception:
            pass

        active_budget = None
        try:
            from app.services.finance.finance_budget_plan_service import (
                finance_budget_plan_service,
            )

            plan = await finance_budget_plan_service.get_active(db)
            if plan is not None:
                budget_income = plan.income_gbp
                if budget_spending <= 0:
                    budget_spending = plan.totals.total_spending_gbp
                active_budget = finance_budget_plan_service.summarise_active(plan)
        except Exception:
            active_budget = None

        income, spending, bills, repayments, flow_source, _configured = resolve_monthly_flow(
            snapshot_present=personal_snap is not None,
            snapshot_income=totals.monthly_income_gbp,
            snapshot_spending=totals.monthly_spending_gbp,
            snapshot_bills=getattr(personal_snap, "household_bills_gbp", 0.0) or 0.0,
            snapshot_repayments=getattr(personal_snap, "debt_repayments_gbp", 0.0) or 0.0,
            open_banking_income=open_banking.income_gbp,
            open_banking_spending=open_banking.spending_gbp,
            cashflow_income=cashflow_income,
            cashflow_spending=cashflow_spending,
            cashflow_bills=cashflow_bills,
            budget_income=budget_income,
            budget_spending=budget_spending,
        )
        director_owes, company_owes = directors_loan_sides(account_views, liability_views)
        personal_bank = round(totals.personal_cash_gbp - totals.personal_overdraft_gbp, 2)
        business_bank = round(totals.business_cash_gbp - totals.business_overdraft_gbp, 2)
        external = external_debt_gbp(
            totals.personal_debt_gbp, totals.business_debt_gbp, totals.directors_loan_gbp
        )
        interest_gbp, interest_incomplete = monthly_interest_from_debts(liability_views)

        from app.services.finance.finance_safe_spend_service import compute_safe_to_spend

        safe_to_spend = compute_safe_to_spend(
            totals=totals,
            personal=personal_snapshot_view(personal_snap),
            business=business_snapshot_view(business_snap),
            liabilities=liability_views,
            flow_source=flow_source,
            resolved_income_gbp=income,
            resolved_spending_gbp=spending,
            resolved_bills_gbp=bills,
        )

        overview = FinanceOverviewResponse(
            personal_bank_balance_gbp=personal_bank,
            business_bank_balance_gbp=business_bank,
            total_personal_debt_gbp=totals.personal_debt_gbp,
            total_business_debt_gbp=totals.business_debt_gbp,
            monthly_income_gbp=income,
            monthly_spending_gbp=spending,
            cash_after_bills_gbp=round(personal_bank - bills, 2),
            vat_reserve_gbp=totals.vat_reserve_gbp,
            corp_tax_reserve_gbp=totals.corp_tax_reserve_gbp,
            vat_reserve_warning=totals.vat_reserve_warning,
            corp_tax_reserve_warning=totals.corp_tax_reserve_warning,
            credit_card_balances_gbp=totals.credit_card_gbp,
            personal_credit_card_balances_gbp=totals.personal_credit_card_gbp,
            loan_balances_gbp=totals.loan_gbp,
            mortgage_balance_gbp=totals.mortgage_gbp,
            pension_value_gbp=totals.pension_gbp,
            directors_loan_gbp=totals.directors_loan_gbp,
            net_worth_estimate_gbp=totals.net_worth_gbp,
            monthly_surplus_gbp=round(income - spending - repayments, 2),
            available_cash_gbp=totals.available_cash_gbp,
            available_credit_gbp=totals.available_credit_gbp,
            credit_limit_gbp=totals.credit_limit_gbp,
            personal_overdraft_gbp=totals.personal_overdraft_gbp,
            business_overdraft_gbp=totals.business_overdraft_gbp,
            total_assets_gbp=totals.total_assets_gbp,
            property_gbp=totals.property_gbp,
            month_budgeted_gbp=budgeted,
            month_actual_gbp=actual,
            active_budget=active_budget,
            insights=[],
            personal_net_worth_gbp=personal_net_worth(
                personal_bank=personal_bank,
                pension=totals.pension_gbp,
                personal_external_debt=totals.personal_debt_gbp,
                director_owes_company=director_owes,
                company_owes_director=company_owes,
            ),
            company_position_gbp=company_position(
                business_bank=business_bank,
                debtors=totals.debtors_gbp,
                vat_reserve=totals.vat_reserve_gbp,
                corp_tax_reserve=totals.corp_tax_reserve_gbp,
                business_external_debt=totals.business_debt_gbp,
                director_owes_company=director_owes,
                company_owes_director=company_owes,
            ),
            director_owes_company_gbp=director_owes,
            company_owes_director_gbp=company_owes,
            external_debt_gbp=external,
            total_debt_gbp=round(
                totals.personal_debt_gbp + totals.business_debt_gbp + totals.directors_loan_gbp,
                2,
            ),
            cash_available_gbp=totals.available_cash_gbp,
            household_bills_gbp=bills,
            monthly_flow_source=flow_source,
            monthly_interest_gbp=interest_gbp,
            monthly_interest_incomplete=interest_incomplete,
            high_interest_debt_gbp=high_interest_debt_gbp(liability_views),
            upcoming_payments=upcoming_payments(liability_views),
            pension_configured=instrument_configured(
                account_views, liability_views, account_type="pension"
            ),
            mortgage_configured=instrument_configured(
                account_views,
                liability_views,
                account_type="mortgage",
                debt_type="mortgage",
            ),
            safe_to_spend=safe_to_spend,
            cash_status=str(safe_to_spend.get("combined", {}).get("status") or "HEALTHY"),
            quickfile_synced_at=await self._sync_stamp(db, "quickfile"),
            lunchflow_synced_at=await self._sync_stamp(db, "lunchflow"),
            liquid_assets_gbp=round(
                totals.available_cash_gbp
                + totals.vat_reserve_gbp
                + totals.corp_tax_reserve_gbp,
                2,
            ),
            long_term_assets_gbp=round(
                totals.property_gbp + totals.pension_gbp + totals.debtors_gbp,
                2,
            ),
            property_value_gbp=totals.property_gbp,
            debtors_gbp=totals.debtors_gbp,
            short_term_debt_gbp=round(
                totals.credit_card_gbp
                + totals.personal_overdraft_gbp
                + totals.business_overdraft_gbp,
                2,
            ),
            long_term_debt_gbp=round(totals.loan_gbp + totals.mortgage_gbp, 2),
            home_equity_gbp=round(totals.property_gbp - totals.mortgage_gbp, 2),
            personal_short_term_debt_gbp=round(
                totals.personal_overdraft_gbp
                + sum(
                    item.balance_gbp
                    for item in liability_views
                    if item.is_active
                    and item.scope == "personal"
                    and item.debt_type in {"credit_card"}
                ),
                2,
            ),
            personal_long_term_debt_gbp=round(
                sum(
                    item.balance_gbp
                    for item in liability_views
                    if item.is_active
                    and item.scope == "personal"
                    and item.debt_type not in {"credit_card", "directors_loan"}
                ),
                2,
            ),
            business_short_term_debt_gbp=round(
                totals.business_overdraft_gbp
                + sum(
                    item.balance_gbp
                    for item in liability_views
                    if item.is_active
                    and item.scope == "business"
                    and item.debt_type in {"credit_card"}
                ),
                2,
            ),
            business_long_term_debt_gbp=round(
                sum(
                    item.balance_gbp
                    for item in liability_views
                    if item.is_active
                    and item.scope == "business"
                    and item.debt_type not in {"credit_card", "directors_loan"}
                ),
                2,
            ),
        )
        if refresh_live:
            overview.insights = await finance_insights_service.refresh_for_overview(
                db, overview
            )
        else:
            existing = await finance_insights_service.generate_and_list(db)
            overview.insights = existing or await finance_insights_service.refresh_for_overview(
                db, overview
            )
        if refresh_live:
            current_month = datetime.now(timezone.utc).strftime("%Y-%m")
            if month == current_month:
                try:
                    from app.services.finance.finance_position_service import (
                        finance_position_service,
                    )

                    await finance_position_service.record_from_overview(
                        db, overview, month=month
                    )
                except Exception:
                    pass
        return overview

    async def _attach_period_flows(
        self,
        db: AsyncSession,
        overview: FinanceOverviewResponse,
        *,
        personal_period: str,
        business_period: str,
    ) -> None:
        from app.schemas.finance import PeriodFlowSummary
        from app.services.finance.finance_ledger_service import finance_ledger_service

        personal = await finance_ledger_service.period_flow_totals(
            db, period=personal_period, scope="personal"
        )
        business = await finance_ledger_service.period_flow_totals(
            db, period=business_period, scope="business"
        )
        personal.pop("month_keys", None)
        business.pop("month_keys", None)
        overview.personal_period_flow = PeriodFlowSummary(**personal)
        overview.business_period_flow = PeriodFlowSummary(**business)

    async def _sync_stamp(self, db: AsyncSession, source: str) -> str | None:
        try:
            if source == "quickfile":
                from app.services.quickfile_settings_service import (
                    quickfile_settings_service,
                )

                return (await quickfile_settings_service.get_status(db)).last_sync_at
            from app.services.lunchflow_settings_service import lunchflow_settings_service

            return (await lunchflow_settings_service.get_status(db)).last_sync_at
        except Exception:
            return None

    async def _open_banking_flow(self, db: AsyncSession) -> MonthlyFlow:
        lunchflow = MonthlyFlow()
        truelayer = MonthlyFlow()
        try:
            from app.services.lunchflow_settings_service import lunchflow_settings_service

            lunchflow = await lunchflow_settings_service.get_monthly_flow(db)
        except Exception:
            pass
        try:
            from app.services.truelayer_settings_service import truelayer_settings_service

            truelayer = await truelayer_settings_service.get_monthly_flow(db)
        except Exception:
            pass
        return pick_open_banking_flow(lunchflow, truelayer)

    async def latest_personal_snapshot(self, db: AsyncSession) -> PersonalFinanceSnapshot | None:
        row = await db.scalar(
            select(PersonalFinanceSnapshotRow)
            .order_by(*_personal_snapshot_order())
            .limit(1)
        )
        return _personal_from_row(row) if row else None

    async def latest_business_snapshot(self, db: AsyncSession) -> BusinessFinanceSnapshot | None:
        row = await db.scalar(
            select(BusinessFinanceSnapshotRow)
            .order_by(*_business_snapshot_order())
            .limit(1)
        )
        return _business_from_row(row) if row else None

    async def create_personal_snapshot(
        self,
        db: AsyncSession,
        body: PersonalFinanceSnapshotCreate,
    ) -> PersonalFinanceSnapshot:
        surplus = (
            body.monthly_income_gbp
            - body.monthly_spending_gbp
            - body.debt_repayments_gbp
        )
        row = PersonalFinanceSnapshotRow(
            snapshot_date=normalize_snapshot_date(body.snapshot_date),
            monthly_income_gbp=body.monthly_income_gbp,
            monthly_spending_gbp=body.monthly_spending_gbp,
            household_bills_gbp=body.household_bills_gbp,
            debt_repayments_gbp=body.debt_repayments_gbp,
            surplus_deficit_gbp=surplus,
            notes=body.notes,
            breakdown_json=json.dumps(body.breakdown),
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _personal_from_row(row)

    async def create_business_snapshot(
        self,
        db: AsyncSession,
        body: BusinessFinanceSnapshotCreate,
    ) -> BusinessFinanceSnapshot:
        profit = body.turnover_gbp - body.expenses_gbp
        cash_draw = body.turnover_gbp - body.expenses_gbp - body.creditors_gbp
        row = BusinessFinanceSnapshotRow(
            snapshot_date=normalize_snapshot_date(body.snapshot_date),
            turnover_gbp=body.turnover_gbp,
            expenses_gbp=body.expenses_gbp,
            vat_reserve_gbp=body.vat_reserve_gbp,
            corp_tax_reserve_gbp=body.corp_tax_reserve_gbp,
            debtors_gbp=body.debtors_gbp,
            creditors_gbp=body.creditors_gbp,
            profit_estimate_gbp=profit,
            cash_available_to_draw_gbp=max(0.0, cash_draw),
            notes=body.notes,
            breakdown_json=json.dumps(body.breakdown),
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _business_from_row(row)

    async def list_personal_snapshots(
        self, db: AsyncSession, limit: int = 12
    ) -> list[PersonalFinanceSnapshot]:
        rows = await db.scalars(
            select(PersonalFinanceSnapshotRow)
            .order_by(*_personal_snapshot_order())
            .limit(limit)
        )
        return [_personal_from_row(r) for r in rows.all()]

    async def list_business_snapshots(
        self, db: AsyncSession, limit: int = 12
    ) -> list[BusinessFinanceSnapshot]:
        rows = await db.scalars(
            select(BusinessFinanceSnapshotRow)
            .order_by(*_business_snapshot_order())
            .limit(limit)
        )
        return [_business_from_row(r) for r in rows.all()]

    async def personal_snapshot_for_month(
        self, db: AsyncSession, month: str
    ) -> PersonalFinanceSnapshot | None:
        row = await db.scalar(
            select(PersonalFinanceSnapshotRow)
            .where(_matches_month(PersonalFinanceSnapshotRow.snapshot_date, month))
            .order_by(*_personal_snapshot_order())
            .limit(1)
        )
        return _personal_from_row(row) if row else None

    async def business_snapshot_for_month(
        self, db: AsyncSession, month: str
    ) -> BusinessFinanceSnapshot | None:
        row = await db.scalar(
            select(BusinessFinanceSnapshotRow)
            .where(_matches_month(BusinessFinanceSnapshotRow.snapshot_date, month))
            .order_by(*_business_snapshot_order())
            .limit(1)
        )
        return _business_from_row(row) if row else None


finance_overview_service = FinanceOverviewService()
