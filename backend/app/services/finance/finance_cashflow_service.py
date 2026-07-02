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
    CashflowForecastResponse,
    FinanceScope,
)
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

    async def build_forecast(
        self,
        db: AsyncSession,
        *,
        horizon_days: int = 30,
    ) -> CashflowForecastResponse:
        overview = await finance_overview_service.get_overview(db)
        entries = await self.list_entries(db, horizon_days=horizon_days)
        starting = overview.personal_bank_balance_gbp + overview.business_bank_balance_gbp

        if not entries:
            entries = await self._seed_from_liabilities(db, horizon_days)

        net = sum(e.amount_gbp for e in entries)
        projected = starting + net
        buffer = getattr(settings, "finance_cash_buffer_gbp", 500.0)
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
            entries=entries,
            cash_pressure_warning=pressure,
            warning_message=warning,
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
