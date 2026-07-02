"""Monthly budget management."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MonthlyBudgetRow
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


class FinanceBudgetService:
    async def list_budget(
        self,
        db: AsyncSession,
        *,
        month: str,
        scope: FinanceScope | None = None,
    ) -> list[MonthlyBudgetLine]:
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


finance_budget_service = FinanceBudgetService()
