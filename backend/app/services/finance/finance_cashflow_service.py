"""Cash flow forecast management — personal and business forecasts kept separate."""

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
    CashflowForecastsResponse,
    DebtType,
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

    async def build_forecasts(
        self,
        db: AsyncSession,
        *,
        horizon_days: int = 30,
    ) -> CashflowForecastsResponse:
        personal = await self.build_forecast_for_scope(
            db, scope=FinanceScope.PERSONAL, horizon_days=horizon_days
        )
        business = await self.build_forecast_for_scope(
            db, scope=FinanceScope.BUSINESS, horizon_days=horizon_days
        )
        return CashflowForecastsResponse(
            horizon_days=horizon_days,
            personal=personal,
            business=business,
        )

    async def build_forecast(
        self,
        db: AsyncSession,
        *,
        horizon_days: int = 30,
    ) -> CashflowForecastsResponse:
        return await self.build_forecasts(db, horizon_days=horizon_days)

    async def build_forecast_for_scope(
        self,
        db: AsyncSession,
        *,
        scope: FinanceScope,
        horizon_days: int = 30,
    ) -> CashflowForecastResponse:
        overview = await finance_overview_service.get_overview(db)
        starting = (
            overview.personal_bank_balance_gbp
            if scope == FinanceScope.PERSONAL
            else overview.business_bank_balance_gbp
        )
        entries = await self.list_entries(db, horizon_days=horizon_days, scope=scope)
        is_stub = False
        stub_message = ""

        if not entries:
            entries = await self._seed_scope_entries(db, scope=scope, horizon_days=horizon_days)
            is_stub = True
            stub_message = (
                "This forecast is auto-generated from monthly snapshots and debt payment days, "
                "not from live bank schedules. Treat figures as indicative until you add confirmed "
                "cash-flow entries."
            )

        net = sum(e.amount_gbp for e in entries)
        projected = starting + net
        buffer = getattr(settings, "finance_cash_buffer_gbp", 500.0)
        pressure = projected < buffer
        scope_label = "Personal" if scope == FinanceScope.PERSONAL else "Business"
        warning = (
            f"{scope_label} projected balance ({projected:.0f} GBP) is below "
            f"your {buffer:.0f} GBP buffer."
            if pressure
            else ""
        )
        return CashflowForecastResponse(
            scope=scope,
            horizon_days=horizon_days,
            starting_balance_gbp=round(starting, 2),
            projected_balance_gbp=round(projected, 2),
            entries=entries,
            cash_pressure_warning=pressure,
            warning_message=warning,
            is_stub=is_stub,
            stub_message=stub_message,
        )

    async def _seed_scope_entries(
        self,
        db: AsyncSession,
        *,
        scope: FinanceScope,
        horizon_days: int,
    ) -> list[CashflowForecastEntry]:
        if scope == FinanceScope.PERSONAL:
            return await self._seed_personal_entries(db, horizon_days)
        return await self._seed_business_entries(db, horizon_days)

    async def _seed_personal_entries(
        self,
        db: AsyncSession,
        horizon_days: int,
    ) -> list[CashflowForecastEntry]:
        liabilities = await finance_liabilities_service.list_liabilities(
            db, scope=FinanceScope.PERSONAL
        )
        personal_snap = await finance_overview_service.latest_personal_snapshot(db)
        created: list[CashflowForecastEntry] = []
        today = datetime.now(timezone.utc).date()

        if personal_snap and personal_snap.monthly_income_gbp > 0:
            created.append(
                await self.create_entry(
                    db,
                    CashflowForecastEntryCreate(
                        scope=FinanceScope.PERSONAL,
                        forecast_date=(today + timedelta(days=28)).isoformat(),
                        horizon_days=horizon_days,
                        entry_type=CashflowEntryType.INCOME,
                        label="Expected salary / income",
                        amount_gbp=personal_snap.monthly_income_gbp,
                        is_confirmed=False,
                        source="snapshot",
                    ),
                )
            )

        if personal_snap and personal_snap.monthly_spending_gbp > 0:
            created.append(
                await self.create_entry(
                    db,
                    CashflowForecastEntryCreate(
                        scope=FinanceScope.PERSONAL,
                        forecast_date=(today + timedelta(days=7)).isoformat(),
                        horizon_days=horizon_days,
                        entry_type=CashflowEntryType.OTHER,
                        label="General spending",
                        amount_gbp=-personal_snap.monthly_spending_gbp,
                        is_confirmed=False,
                        source="snapshot",
                    ),
                )
            )

        if personal_snap and personal_snap.household_bills_gbp > 0:
            created.append(
                await self.create_entry(
                    db,
                    CashflowForecastEntryCreate(
                        scope=FinanceScope.PERSONAL,
                        forecast_date=(today + timedelta(days=14)).isoformat(),
                        horizon_days=horizon_days,
                        entry_type=CashflowEntryType.BILL,
                        label="Household bills",
                        amount_gbp=-personal_snap.household_bills_gbp,
                        is_confirmed=False,
                        source="snapshot",
                    ),
                )
            )

        for liability in liabilities:
            if liability.debt_type == DebtType.MORTGAGE:
                continue
            payment = liability.minimum_payment_gbp + liability.overpayment_gbp
            if payment <= 0:
                continue
            day = liability.payment_day or 1
            forecast_day = today.replace(day=min(day, 28))
            if forecast_day <= today:
                forecast_day = forecast_day + timedelta(days=30)
            created.append(
                await self.create_entry(
                    db,
                    CashflowForecastEntryCreate(
                        scope=FinanceScope.PERSONAL,
                        forecast_date=forecast_day.isoformat(),
                        horizon_days=horizon_days,
                        entry_type=CashflowEntryType.DEBT,
                        label=f"Debt payment — {liability.name}",
                        amount_gbp=-payment,
                        is_confirmed=False,
                        source="liability",
                    ),
                )
            )

        return created

    async def _seed_business_entries(
        self,
        db: AsyncSession,
        horizon_days: int,
    ) -> list[CashflowForecastEntry]:
        business_snap = await finance_overview_service.latest_business_snapshot(db)
        created: list[CashflowForecastEntry] = []
        today = datetime.now(timezone.utc).date()

        if business_snap and business_snap.turnover_gbp > 0:
            created.append(
                await self.create_entry(
                    db,
                    CashflowForecastEntryCreate(
                        scope=FinanceScope.BUSINESS,
                        forecast_date=(today + timedelta(days=21)).isoformat(),
                        horizon_days=horizon_days,
                        entry_type=CashflowEntryType.INCOME,
                        label="Expected client receipts / turnover",
                        amount_gbp=business_snap.turnover_gbp,
                        is_confirmed=False,
                        source="snapshot",
                    ),
                )
            )

        if business_snap and business_snap.expenses_gbp > 0:
            created.append(
                await self.create_entry(
                    db,
                    CashflowForecastEntryCreate(
                        scope=FinanceScope.BUSINESS,
                        forecast_date=(today + timedelta(days=10)).isoformat(),
                        horizon_days=horizon_days,
                        entry_type=CashflowEntryType.BILL,
                        label="Business expenses",
                        amount_gbp=-business_snap.expenses_gbp,
                        is_confirmed=False,
                        source="snapshot",
                    ),
                )
            )

        if business_snap and business_snap.creditors_gbp > 0:
            created.append(
                await self.create_entry(
                    db,
                    CashflowForecastEntryCreate(
                        scope=FinanceScope.BUSINESS,
                        forecast_date=(today + timedelta(days=18)).isoformat(),
                        horizon_days=horizon_days,
                        entry_type=CashflowEntryType.BILL,
                        label="Supplier / creditor payments",
                        amount_gbp=-business_snap.creditors_gbp,
                        is_confirmed=False,
                        source="snapshot",
                    ),
                )
            )

        vat_estimate = (business_snap.expenses_gbp * 0.2) if business_snap else 0.0
        if business_snap and vat_estimate > 0:
            created.append(
                await self.create_entry(
                    db,
                    CashflowForecastEntryCreate(
                        scope=FinanceScope.BUSINESS,
                        forecast_date=(today + timedelta(days=horizon_days - 5)).isoformat(),
                        horizon_days=horizon_days,
                        entry_type=CashflowEntryType.TAX_VAT,
                        label="VAT payment (estimate)",
                        amount_gbp=-round(vat_estimate, 2),
                        is_confirmed=False,
                        source="snapshot",
                    ),
                )
            )

        profit = (business_snap.turnover_gbp - business_snap.expenses_gbp) if business_snap else 0.0
        if business_snap and profit > 0:
            created.append(
                await self.create_entry(
                    db,
                    CashflowForecastEntryCreate(
                        scope=FinanceScope.BUSINESS,
                        forecast_date=(today + timedelta(days=horizon_days - 2)).isoformat(),
                        horizon_days=horizon_days,
                        entry_type=CashflowEntryType.TAX_VAT,
                        label="Corporation tax provision (estimate)",
                        amount_gbp=-round(profit * 0.19, 2),
                        is_confirmed=False,
                        source="snapshot",
                    ),
                )
            )

        liabilities = await finance_liabilities_service.list_liabilities(
            db, scope=FinanceScope.BUSINESS
        )
        for liability in liabilities:
            payment = liability.minimum_payment_gbp + liability.overpayment_gbp
            if payment <= 0:
                continue
            day = liability.payment_day or 15
            forecast_day = today.replace(day=min(day, 28))
            if forecast_day <= today:
                forecast_day = forecast_day + timedelta(days=30)
            created.append(
                await self.create_entry(
                    db,
                    CashflowForecastEntryCreate(
                        scope=FinanceScope.BUSINESS,
                        forecast_date=forecast_day.isoformat(),
                        horizon_days=horizon_days,
                        entry_type=CashflowEntryType.DEBT,
                        label=f"Business debt — {liability.name}",
                        amount_gbp=-payment,
                        is_confirmed=False,
                        source="liability",
                    ),
                )
            )

        return created


finance_cashflow_service = FinanceCashflowService()
