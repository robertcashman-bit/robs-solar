"""Monthly budget management."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceTransactionRow, MonthlyBudgetRow
from app.schemas.finance import (
    FinanceScope,
    MonthlyBudgetLine,
    MonthlyBudgetLineCreate,
    MonthlyBudgetLineUpdate,
)


def _to_schema(row: MonthlyBudgetRow) -> MonthlyBudgetLine:
    return MonthlyBudgetLine(
        id=row.id,
        scope=FinanceScope(row.scope),
        month=row.month,
        category=row.category,
        budgeted_gbp=row.budgeted_gbp,
        actual_gbp=row.actual_gbp,
        remaining_gbp=round(row.budgeted_gbp - row.actual_gbp, 2),
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _previous_month(month: str) -> str:
    year, mon = int(month[:4]), int(month[5:7])
    if mon == 1:
        return f"{year - 1}-12"
    return f"{year}-{mon - 1:02d}"


def _month_date_bounds(month: str) -> tuple[str, str]:
    year, mon = int(month[:4]), int(month[5:7])
    last = monthrange(year, mon)[1]
    return f"{month}-01", f"{month}-{last:02d}"


class FinanceBudgetService:
    async def list_budget(
        self,
        db: AsyncSession,
        *,
        month: str,
        scope: FinanceScope | None = None,
        refresh_actuals: bool = True,
    ) -> list[MonthlyBudgetLine]:
        if refresh_actuals:
            await self.refresh_actuals_from_transactions(db, month=month, scope=scope)
        stmt = (
            select(MonthlyBudgetRow)
            .where(MonthlyBudgetRow.month == month)
            .order_by(MonthlyBudgetRow.category)
        )
        if scope is not None:
            stmt = stmt.where(MonthlyBudgetRow.scope == scope.value)
        rows = await db.scalars(stmt)
        return [_to_schema(r) for r in rows.all()]

    async def upsert_line(
        self,
        db: AsyncSession,
        body: MonthlyBudgetLineCreate,
    ) -> MonthlyBudgetLine:
        existing = await db.scalar(
            select(MonthlyBudgetRow).where(
                MonthlyBudgetRow.scope == body.scope.value,
                MonthlyBudgetRow.month == body.month,
                MonthlyBudgetRow.category == body.category,
            )
        )
        now = datetime.now(timezone.utc)
        if existing:
            existing.budgeted_gbp = body.budgeted_gbp
            existing.actual_gbp = body.actual_gbp
            existing.notes = body.notes
            existing.updated_at = now
            row = existing
        else:
            row = MonthlyBudgetRow(
                scope=body.scope.value,
                month=body.month,
                category=body.category,
                budgeted_gbp=body.budgeted_gbp,
                actual_gbp=body.actual_gbp,
                notes=body.notes,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)

    async def update_line(
        self,
        db: AsyncSession,
        line_id: int,
        body: MonthlyBudgetLineUpdate,
    ) -> MonthlyBudgetLine | None:
        row = await db.get(MonthlyBudgetRow, line_id)
        if row is None:
            return None
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)

    async def seed_from_previous(
        self,
        db: AsyncSession,
        *,
        month: str,
        scope: FinanceScope,
    ) -> list[MonthlyBudgetLine]:
        """Copy prior-month categories/budgeted amounts when the target month is empty."""
        existing = await self.list_budget(
            db, month=month, scope=scope, refresh_actuals=False
        )
        if existing:
            return existing

        prev = _previous_month(month)
        prior = await self.list_budget(db, month=prev, scope=scope, refresh_actuals=False)
        if not prior:
            return []

        now = datetime.now(timezone.utc)
        for line in prior:
            db.add(
                MonthlyBudgetRow(
                    scope=scope.value,
                    month=month,
                    category=line.category,
                    budgeted_gbp=line.budgeted_gbp,
                    actual_gbp=0.0,
                    notes=line.notes or "Seeded from previous month",
                    created_at=now,
                    updated_at=now,
                )
            )
        await db.commit()
        return await self.list_budget(db, month=month, scope=scope, refresh_actuals=True)

    async def refresh_actuals_from_transactions(
        self,
        db: AsyncSession,
        *,
        month: str,
        scope: FinanceScope | None = None,
    ) -> None:
        """Set each budget line's actual_gbp from matching transaction categories."""
        stmt = select(MonthlyBudgetRow).where(MonthlyBudgetRow.month == month)
        if scope is not None:
            stmt = stmt.where(MonthlyBudgetRow.scope == scope.value)
        lines = list((await db.scalars(stmt)).all())
        if not lines:
            return

        start, end = _month_date_bounds(month)
        tx_stmt = select(FinanceTransactionRow).where(
            FinanceTransactionRow.transaction_date >= start,
            FinanceTransactionRow.transaction_date <= end,
        )
        txs = list((await db.scalars(tx_stmt)).all())
        spent_by_category: dict[str, float] = {}
        for tx in txs:
            cat = (tx.category or "").strip() or "Uncategorised"
            # Spending is negative amounts; store as positive actual spend.
            if tx.amount_gbp < 0:
                spent_by_category[cat] = spent_by_category.get(cat, 0.0) + abs(tx.amount_gbp)

        now = datetime.now(timezone.utc)
        changed = False
        for line in lines:
            actual = round(spent_by_category.get(line.category, 0.0), 2)
            if abs(line.actual_gbp - actual) > 0.001:
                line.actual_gbp = actual
                line.updated_at = now
                changed = True
        if changed:
            await db.commit()


finance_budget_service = FinanceBudgetService()
