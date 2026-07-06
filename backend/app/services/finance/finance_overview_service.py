"""Aggregated finance overview dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BusinessFinanceSnapshotRow, PersonalFinanceSnapshotRow
from app.schemas.finance import (
    BusinessFinanceSnapshot,
    BusinessFinanceSnapshotCreate,
    FinanceAccount,
    FinanceAccountType,
    FinanceOverviewResponse,
    FinanceScope,
    PersonalFinanceSnapshot,
    PersonalFinanceSnapshotCreate,
)
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_balance_service import build_balance_breakdown
from app.services.finance.finance_insights_service import finance_insights_service
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.quickfile_reports_service import quickfile_reports_service


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
        breakdown=json.loads(row.breakdown_json or "{}"),
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
        breakdown=json.loads(row.breakdown_json or "{}"),
        created_at=row.created_at,
    )


def _historic_fields(
    accounts: list[FinanceAccount],
    *,
    personal_snap: PersonalFinanceSnapshot | None,
    has_personal_liabilities: bool,
) -> list[str]:
    fields: list[str] = []

    personal_current = [
        a
        for a in accounts
        if a.scope == FinanceScope.PERSONAL and a.account_type == FinanceAccountType.CURRENT
    ]
    if personal_current and all(a.is_historic for a in personal_current):
        fields.append("personal_bank_balance_gbp")

    business_current = [
        a
        for a in accounts
        if a.scope == FinanceScope.BUSINESS and a.account_type == FinanceAccountType.CURRENT
    ]
    if business_current and any(a.is_historic for a in business_current):
        fields.append("business_bank_balance_gbp")

    if personal_snap is not None:
        fields.extend(
            [
                "personal_monthly_income_gbp",
                "monthly_income_gbp",
                "monthly_spending_gbp",
                "monthly_surplus_gbp",
                "cash_after_bills_gbp",
            ]
        )

    if has_personal_liabilities:
        fields.extend(
            [
                "total_personal_debt_gbp",
                "personal_short_term_debt_gbp",
                "personal_long_term_debt_gbp",
                "short_term_debt_gbp",
                "long_term_debt_gbp",
            ]
        )

    property_accounts = [a for a in accounts if a.account_type == FinanceAccountType.PROPERTY]
    if property_accounts and all(a.is_historic for a in property_accounts):
        fields.extend(["property_value_gbp", "home_equity_gbp", "long_term_assets_gbp"])

    pension_accounts = [a for a in accounts if a.account_type == FinanceAccountType.PENSION]
    if pension_accounts and all(a.is_historic for a in pension_accounts):
        fields.append("pension_value_gbp")

    if has_personal_liabilities:
        fields.append("credit_card_balances_gbp")
        fields.append("loan_balances_gbp")
        fields.append("mortgage_balance_gbp")

    dl_accounts = [a for a in accounts if a.account_type == FinanceAccountType.DIRECTORS_LOAN]
    if dl_accounts and any(a.is_historic for a in dl_accounts):
        fields.append("directors_loan_gbp")

    vat_accounts = [a for a in accounts if a.account_type == FinanceAccountType.VAT_RESERVE]
    if vat_accounts and any(a.is_historic for a in vat_accounts):
        fields.append("vat_reserve_gbp")

    corp_accounts = [a for a in accounts if a.account_type == FinanceAccountType.CORP_TAX_RESERVE]
    if corp_accounts and any(a.is_historic for a in corp_accounts):
        fields.append("corp_tax_reserve_gbp")

    return sorted(set(fields))


class FinanceOverviewService:
    async def get_overview(self, db: AsyncSession) -> FinanceOverviewResponse:
        accounts = await finance_accounts_service.list_accounts(db)
        liabilities = await finance_liabilities_service.list_liabilities(db)
        personal_snap = await self.latest_personal_snapshot(db)
        business_snap = await self.latest_business_snapshot(db)
        qf_reports = await quickfile_reports_service.get_stored_reports(db)

        personal_bank = finance_accounts_service.sum_scope_balance(
            accounts, FinanceScope.PERSONAL, FinanceAccountType.CURRENT
        )
        business_bank = finance_accounts_service.sum_scope_balance(
            accounts, FinanceScope.BUSINESS, FinanceAccountType.CURRENT
        )

        debtors = (
            business_snap.debtors_gbp
            if business_snap
            else finance_accounts_service.sum_by_type(accounts, FinanceAccountType.DEBTORS)
        )
        breakdown = build_balance_breakdown(
            accounts,
            liabilities,
            debtors_gbp=debtors,
        )

        personal_liabilities = [
            debt for debt in liabilities if debt.scope == FinanceScope.PERSONAL
        ]

        monthly_income = personal_snap.monthly_income_gbp if personal_snap else 0.0
        monthly_spending = personal_snap.monthly_spending_gbp if personal_snap else 0.0
        household_bills = personal_snap.household_bills_gbp if personal_snap else 0.0
        cash_after_bills = personal_bank - household_bills

        vat_reserve = (
            business_snap.vat_reserve_gbp
            if business_snap
            else finance_accounts_service.sum_by_type(accounts, FinanceAccountType.VAT_RESERVE)
        )
        corp_tax_reserve = (
            business_snap.corp_tax_reserve_gbp
            if business_snap
            else finance_accounts_service.sum_by_type(
                accounts, FinanceAccountType.CORP_TAX_RESERVE
            )
        )

        monthly_surplus = monthly_income - monthly_spending - (
            personal_snap.debt_repayments_gbp if personal_snap else 0.0
        )

        personal_monthly_income = round(monthly_income, 2)
        business_turnover = 0.0
        business_expenses = 0.0
        business_net_profit = 0.0
        business_ytd_turnover = 0.0
        business_ytd_net_profit = 0.0
        business_from_qf = False
        qf_synced_at: str | None = None

        if qf_reports and qf_reports.profit_and_loss_month:
            pl = qf_reports.profit_and_loss_month
            business_turnover = pl.turnover_gbp
            business_expenses = pl.expenses_gbp
            business_net_profit = pl.net_profit_gbp
            business_from_qf = True
            qf_synced_at = qf_reports.synced_at
        elif business_snap:
            business_turnover = business_snap.turnover_gbp
            business_expenses = business_snap.expenses_gbp
            business_net_profit = business_snap.profit_estimate_gbp

        if qf_reports and qf_reports.profit_and_loss_ytd:
            business_ytd_turnover = qf_reports.profit_and_loss_ytd.turnover_gbp
            business_ytd_net_profit = qf_reports.profit_and_loss_ytd.net_profit_gbp
            business_from_qf = True
            qf_synced_at = qf_reports.synced_at or qf_synced_at

        vat_warning = vat_reserve < (
            business_snap.expenses_gbp * 0.2 if business_snap else 500
        )
        corp_warning = corp_tax_reserve < (
            business_snap.profit_estimate_gbp * 0.19 if business_snap else 500
        )

        overview = FinanceOverviewResponse(
            personal_bank_balance_gbp=round(personal_bank, 2),
            business_bank_balance_gbp=round(business_bank, 2),
            total_personal_debt_gbp=breakdown.personal_total_debt_gbp,
            total_business_debt_gbp=breakdown.business_total_debt_gbp,
            monthly_income_gbp=round(monthly_income, 2),
            monthly_spending_gbp=round(monthly_spending, 2),
            cash_after_bills_gbp=round(cash_after_bills, 2),
            vat_reserve_gbp=round(vat_reserve, 2),
            corp_tax_reserve_gbp=round(corp_tax_reserve, 2),
            vat_reserve_warning=vat_warning,
            corp_tax_reserve_warning=corp_warning,
            credit_card_balances_gbp=breakdown.credit_card_balances_gbp,
            loan_balances_gbp=breakdown.loan_balances_gbp,
            mortgage_balance_gbp=breakdown.mortgage_balance_gbp,
            pension_value_gbp=breakdown.pension_value_gbp,
            directors_loan_gbp=breakdown.directors_loan_gbp,
            liquid_assets_gbp=breakdown.liquid_assets_gbp,
            long_term_assets_gbp=breakdown.long_term_assets_gbp,
            property_value_gbp=breakdown.property_value_gbp,
            debtors_gbp=breakdown.debtors_gbp,
            total_assets_gbp=breakdown.total_assets_gbp,
            short_term_debt_gbp=breakdown.short_term_debt_gbp,
            long_term_debt_gbp=breakdown.long_term_debt_gbp,
            total_debt_gbp=breakdown.total_debt_gbp,
            home_equity_gbp=breakdown.home_equity_gbp,
            personal_short_term_debt_gbp=breakdown.personal_short_term_debt_gbp,
            personal_long_term_debt_gbp=breakdown.personal_long_term_debt_gbp,
            business_short_term_debt_gbp=breakdown.business_short_term_debt_gbp,
            business_long_term_debt_gbp=breakdown.business_long_term_debt_gbp,
            net_worth_estimate_gbp=breakdown.net_worth_estimate_gbp,
            monthly_surplus_gbp=round(monthly_surplus, 2),
            personal_monthly_income_gbp=personal_monthly_income,
            business_monthly_turnover_gbp=round(business_turnover, 2),
            business_monthly_expenses_gbp=round(business_expenses, 2),
            business_monthly_net_profit_gbp=round(business_net_profit, 2),
            business_ytd_turnover_gbp=round(business_ytd_turnover, 2),
            business_ytd_net_profit_gbp=round(business_ytd_net_profit, 2),
            business_income_from_quickfile=business_from_qf,
            quickfile_reports_at=qf_synced_at,
            historic_fields=_historic_fields(
                accounts,
                personal_snap=personal_snap,
                has_personal_liabilities=bool(personal_liabilities),
            ),
            insights=[],
        )
        overview.insights = await finance_insights_service.refresh_for_overview(db, overview)
        return overview

    async def latest_personal_snapshot(self, db: AsyncSession) -> PersonalFinanceSnapshot | None:
        row = await db.scalar(
            select(PersonalFinanceSnapshotRow)
            .order_by(PersonalFinanceSnapshotRow.snapshot_date.desc())
            .limit(1)
        )
        return _personal_from_row(row) if row else None

    async def latest_business_snapshot(self, db: AsyncSession) -> BusinessFinanceSnapshot | None:
        row = await db.scalar(
            select(BusinessFinanceSnapshotRow)
            .order_by(BusinessFinanceSnapshotRow.snapshot_date.desc())
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
            snapshot_date=body.snapshot_date,
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
            snapshot_date=body.snapshot_date,
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
            .order_by(PersonalFinanceSnapshotRow.snapshot_date.desc())
            .limit(limit)
        )
        return [_personal_from_row(r) for r in rows.all()]

    async def list_business_snapshots(
        self, db: AsyncSession, limit: int = 12
    ) -> list[BusinessFinanceSnapshot]:
        rows = await db.scalars(
            select(BusinessFinanceSnapshotRow)
            .order_by(BusinessFinanceSnapshotRow.snapshot_date.desc())
            .limit(limit)
        )
        return [_business_from_row(r) for r in rows.all()]


finance_overview_service = FinanceOverviewService()
