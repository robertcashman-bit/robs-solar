"""Cash flow forecast management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CashflowForecastRow
from app.schemas.finance import (
    CashflowEntryType,
    CashflowForecastEntry,
    CashflowForecastEntryCreate,
    CashflowForecastEntryUpdate,
    CashflowForecastResponse,
    CashflowScopeColumn,
    FinanceScope,
)
from app.services.finance.finance_calc import is_repayable_debt
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service


def _to_schema(row: CashflowForecastRow) -> CashflowForecastEntry:
    return CashflowForecastEntry(
        id=row.id,
        scope=FinanceScope(row.scope),
        forecast_date=row.forecast_date,
        horizon_days=row.horizon_days,
        entry_type=CashflowEntryType(row.entry_type),
        label=row.label,
        amount_gbp=row.amount_gbp,
        is_confirmed=row.is_confirmed,
        source=row.source,
        created_at=row.created_at,
    )


class FinanceCashflowService:
    async def list_entries(
        self,
        db: AsyncSession,
        *,
        horizon_days: int = 30,
        scope: FinanceScope | None = None,
    ) -> list[CashflowForecastEntry]:
        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=horizon_days)
        stmt = (
            select(CashflowForecastRow)
            .where(CashflowForecastRow.horizon_days == horizon_days)
            .order_by(CashflowForecastRow.forecast_date)
        )
        if scope is not None:
            stmt = stmt.where(CashflowForecastRow.scope == scope.value)
        rows = await db.scalars(stmt)
        entries = [_to_schema(r) for r in rows.all()]
        return [e for e in entries if e.forecast_date <= end.isoformat()]

    async def create_entry(
        self,
        db: AsyncSession,
        body: CashflowForecastEntryCreate,
    ) -> CashflowForecastEntry:
        row = CashflowForecastRow(
            scope=body.scope.value,
            forecast_date=body.forecast_date,
            horizon_days=body.horizon_days,
            entry_type=body.entry_type.value,
            label=body.label,
            amount_gbp=body.amount_gbp,
            is_confirmed=body.is_confirmed,
            source=body.source,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)

    async def update_entry(
        self,
        db: AsyncSession,
        entry_id: int,
        body: CashflowForecastEntryUpdate,
    ) -> CashflowForecastEntry | None:
        row = await db.get(CashflowForecastRow, entry_id)
        if row is None:
            return None
        data = body.model_dump(exclude_unset=True)
        if "entry_type" in data and data["entry_type"] is not None:
            data["entry_type"] = (
                data["entry_type"].value
                if hasattr(data["entry_type"], "value")
                else data["entry_type"]
            )
        for field, value in data.items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)

    async def month_flow(self, db: AsyncSession, month: str) -> tuple[float, float, float]:
        """Confirmed income, spending, and bills dated in ``month`` (YYYY-MM)."""
        rows = await db.scalars(
            select(CashflowForecastRow).where(
                CashflowForecastRow.is_confirmed.is_(True),
                CashflowForecastRow.forecast_date.startswith(month),
            )
        )
        income = 0.0
        spending = 0.0
        bills = 0.0
        for row in rows.all():
            amount = float(row.amount_gbp or 0)
            if row.entry_type == CashflowEntryType.INCOME.value:
                if amount > 0:
                    income += amount
                continue
            spending += abs(amount)
            if row.entry_type == CashflowEntryType.BILL.value:
                bills += abs(amount)
        return round(income, 2), round(spending, 2), round(bills, 2)

    async def delete_entry(self, db: AsyncSession, entry_id: int) -> bool:
        row = await db.get(CashflowForecastRow, entry_id)
        if row is None:
            return False
        await db.delete(row)
        await db.commit()
        return True

    async def confirmed_month_flow(
        self, db: AsyncSession, month: str
    ) -> tuple[float, float, float]:
        return await self.month_flow(db, month)

    async def build_forecast(
        self,
        db: AsyncSession,
        *,
        horizon_days: int = 30,
        scope: FinanceScope | None = None,
    ) -> CashflowForecastResponse:
        overview = await finance_overview_service.get_overview(db)
        # Seed only when the horizon has no stored forecasts at all. An empty
        # scoped filter must not re-seed and duplicate other scopes' rows.
        all_entries = await self.list_entries(db, horizon_days=horizon_days, scope=None)
        if not all_entries:
            all_entries = await self._seed_from_liabilities(db, horizon_days)
        entries = (
            [item for item in all_entries if item.scope == scope]
            if scope is not None
            else all_entries
        )

        personal_entries = [item for item in entries if item.scope == FinanceScope.PERSONAL]
        business_entries = [item for item in entries if item.scope == FinanceScope.BUSINESS]
        buffer = getattr(settings, "finance_cash_buffer_gbp", 500.0)

        def _column(
            column_scope: FinanceScope,
            starting: float,
            column_entries: list[CashflowForecastEntry],
        ) -> CashflowScopeColumn:
            projected = starting + sum(item.amount_gbp for item in column_entries)
            return CashflowScopeColumn(
                scope=column_scope,
                starting_balance_gbp=round(starting, 2),
                projected_balance_gbp=round(projected, 2),
                entries=column_entries,
                cash_pressure_warning=projected < buffer,
            )

        personal_col = _column(
            FinanceScope.PERSONAL,
            overview.personal_bank_balance_gbp,
            personal_entries,
        )
        business_col = _column(
            FinanceScope.BUSINESS,
            overview.business_bank_balance_gbp,
            business_entries,
        )

        if scope == FinanceScope.PERSONAL:
            columns = [personal_col]
            starting = personal_col.starting_balance_gbp
            projected = personal_col.projected_balance_gbp
            shown = personal_entries
        elif scope == FinanceScope.BUSINESS:
            columns = [business_col]
            starting = business_col.starting_balance_gbp
            projected = business_col.projected_balance_gbp
            shown = business_entries
        else:
            columns = [personal_col, business_col]
            starting = personal_col.starting_balance_gbp + business_col.starting_balance_gbp
            projected = personal_col.projected_balance_gbp + business_col.projected_balance_gbp
            shown = entries

        pressure = projected < buffer
        warning = (
            f"Projected balance ({projected:.0f} GBP) is below your {buffer:.0f} GBP buffer."
            if pressure
            else ""
        )
        return CashflowForecastResponse(
            horizon_days=horizon_days,
            starting_balance_gbp=round(starting, 2),
            projected_balance_gbp=round(projected, 2),
            entries=shown,
            cash_pressure_warning=pressure,
            warning_message=warning,
            columns=columns,
        )

    async def _seed_from_liabilities(
        self,
        db: AsyncSession,
        horizon_days: int,
    ) -> list[CashflowForecastEntry]:
        """Build forecast entries from liabilities when none stored."""
        liabilities = await finance_liabilities_service.list_liabilities(db)
        personal_snap = await finance_overview_service.latest_personal_snapshot(db)
        created: list[CashflowForecastEntry] = []
        today = datetime.now(timezone.utc).date()

        if personal_snap and personal_snap.monthly_income_gbp > 0:
            body = CashflowForecastEntryCreate(
                scope=FinanceScope.PERSONAL,
                forecast_date=(today + timedelta(days=28)).isoformat(),
                horizon_days=horizon_days,
                entry_type=CashflowEntryType.INCOME,
                label="Expected salary / income",
                amount_gbp=personal_snap.monthly_income_gbp,
                is_confirmed=False,
            )
            created.append(await self.create_entry(db, body))

        if personal_snap and personal_snap.household_bills_gbp > 0:
            body = CashflowForecastEntryCreate(
                scope=FinanceScope.PERSONAL,
                forecast_date=(today + timedelta(days=14)).isoformat(),
                horizon_days=horizon_days,
                entry_type=CashflowEntryType.BILL,
                label="Household bills",
                amount_gbp=-personal_snap.household_bills_gbp,
                is_confirmed=False,
            )
            created.append(await self.create_entry(db, body))

        for liability in liabilities:
            if not is_repayable_debt(liability):
                continue
            payment = liability.minimum_payment_gbp + liability.overpayment_gbp
            if payment <= 0:
                continue
            day = liability.payment_day or 1
            forecast_day = today.replace(day=min(day, 28))
            if forecast_day <= today:
                forecast_day = forecast_day + timedelta(days=30)
            body = CashflowForecastEntryCreate(
                scope=liability.scope,
                forecast_date=forecast_day.isoformat(),
                horizon_days=horizon_days,
                entry_type=CashflowEntryType.DEBT,
                label=f"Debt payment — {liability.name}",
                amount_gbp=-payment,
                is_confirmed=False,
            )
            created.append(await self.create_entry(db, body))

        return created


finance_cashflow_service = FinanceCashflowService()
