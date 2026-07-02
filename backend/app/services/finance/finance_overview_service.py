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
    FinanceAccountType,
    FinanceOverviewResponse,
    FinanceScope,
    PersonalFinanceSnapshot,
    PersonalFinanceSnapshotCreate,
)
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_insights_service import finance_insights_service
from app.services.finance.finance_liabilities_service import finance_liabilities_service


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


class FinanceOverviewService:
    async def get_overview(self, db: AsyncSession) -> FinanceOverviewResponse:
        accounts = await finance_accounts_service.list_accounts(db)
        liabilities = await finance_liabilities_service.list_liabilities(db)
        personal_snap = await self.latest_personal_snapshot(db)
        business_snap = await self.latest_business_snapshot(db)

        personal_bank = finance_accounts_service.sum_scope_balance(
            accounts, FinanceScope.PERSONAL, FinanceAccountType.CURRENT
        )
        business_bank = finance_accounts_service.sum_scope_balance(
            accounts, FinanceScope.BUSINESS, FinanceAccountType.CURRENT
        )
        credit_cards = (
            finance_accounts_service.sum_by_type(accounts, FinanceAccountType.CREDIT_CARD)
            + sum(
                l.balance_gbp
                for l in liabilities
                if l.debt_type.value == "credit_card"
            )
        )
        loans = (
            finance_accounts_service.sum_by_type(accounts, FinanceAccountType.LOAN)
            + sum(l.balance_gbp for l in liabilities if l.debt_type.value in ("loan", "business_loan"))
        )
        mortgage = (
            finance_accounts_service.sum_by_type(accounts, FinanceAccountType.MORTGAGE)
            + sum(l.balance_gbp for l in liabilities if l.debt_type.value == "mortgage")
        )
        pension = finance_accounts_service.sum_by_type(accounts, FinanceAccountType.PENSION)
        directors_loan = (
            finance_accounts_service.sum_by_type(accounts, FinanceAccountType.DIRECTORS_LOAN)
            + sum(l.balance_gbp for l in liabilities if l.debt_type.value == "directors_loan")
        )

        total_personal_debt = finance_liabilities_service.total_debt(liabilities, FinanceScope.PERSONAL)
        total_business_debt = finance_liabilities_service.total_debt(liabilities, FinanceScope.BUSINESS)

        monthly_income = personal_snap.monthly_income_gbp if personal_snap else 0.0
        monthly_spending = personal_snap.monthly_spending_gbp if personal_snap else 0.0
        household_bills = personal_snap.household_bills_gbp if personal_snap else 0.0
        cash_after_bills = personal_bank - household_bills

        vat_reserve = business_snap.vat_reserve_gbp if business_snap else finance_accounts_service.sum_by_type(
            accounts, FinanceAccountType.VAT_RESERVE
        )
        corp_tax_reserve = (
            business_snap.corp_tax_reserve_gbp
            if business_snap
            else finance_accounts_service.sum_by_type(accounts, FinanceAccountType.CORP_TAX_RESERVE)
        )

        assets = personal_bank + business_bank + pension + (
            business_snap.debtors_gbp if business_snap else finance_accounts_service.sum_by_type(
                accounts, FinanceAccountType.DEBTORS
            )
        )
        debts = (
            total_personal_debt
            + total_business_debt
            + credit_cards
            + loans
            + mortgage
            + directors_loan
        )
        net_worth = assets - debts

        monthly_surplus = monthly_income - monthly_spending - (
            personal_snap.debt_repayments_gbp if personal_snap else 0.0
        )

        vat_warning = vat_reserve < (business_snap.expenses_gbp * 0.2 if business_snap else 500)
        corp_warning = corp_tax_reserve < (business_snap.profit_estimate_gbp * 0.19 if business_snap else 500)

        overview = FinanceOverviewResponse(
            personal_bank_balance_gbp=round(personal_bank, 2),
            business_bank_balance_gbp=round(business_bank, 2),
            total_personal_debt_gbp=round(total_personal_debt, 2),
            total_business_debt_gbp=round(total_business_debt, 2),
            monthly_income_gbp=round(monthly_income, 2),
            monthly_spending_gbp=round(monthly_spending, 2),
            cash_after_bills_gbp=round(cash_after_bills, 2),
            vat_reserve_gbp=round(vat_reserve, 2),
            corp_tax_reserve_gbp=round(corp_tax_reserve, 2),
            vat_reserve_warning=vat_warning,
            corp_tax_reserve_warning=corp_warning,
            credit_card_balances_gbp=round(credit_cards, 2),
            loan_balances_gbp=round(loans, 2),
            mortgage_balance_gbp=round(mortgage, 2),
            pension_value_gbp=round(pension, 2),
            directors_loan_gbp=round(directors_loan, 2),
            net_worth_estimate_gbp=round(net_worth, 2),
            monthly_surplus_gbp=round(monthly_surplus, 2),
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

    async def list_personal_snapshots(self, db: AsyncSession, limit: int = 12) -> list[PersonalFinanceSnapshot]:
        rows = await db.scalars(
            select(PersonalFinanceSnapshotRow)
            .order_by(PersonalFinanceSnapshotRow.snapshot_date.desc())
            .limit(limit)
        )
        return [_personal_from_row(r) for r in rows.all()]

    async def list_business_snapshots(self, db: AsyncSession, limit: int = 12) -> list[BusinessFinanceSnapshot]:
        rows = await db.scalars(
            select(BusinessFinanceSnapshotRow)
            .order_by(BusinessFinanceSnapshotRow.snapshot_date.desc())
            .limit(limit)
        )
        return [_business_from_row(r) for r in rows.all()]


finance_overview_service = FinanceOverviewService()
