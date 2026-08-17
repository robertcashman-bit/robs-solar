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
from app.services.finance.budget_suggestion_service import (
    BUSINESS_CATEGORIES,
    PERSONAL_CATEGORIES,
)

UNRECORDED_ACTUAL_NOTES = frozenset(
    {"Starter category", "From active budget", "Unrecorded actual"}
)


def recorded_actual_gbp(row: MonthlyBudgetRow) -> float | None:
    """Blank/unseeded actuals stay missing — never treated as £0 spend."""
    notes = (row.notes or "").strip()
    if notes in UNRECORDED_ACTUAL_NOTES and float(row.actual_gbp or 0) == 0:
        return None
    if row.actual_gbp is None:
        return None
    return float(row.actual_gbp)


def _to_schema(row: MonthlyBudgetRow) -> MonthlyBudgetLine:
    recorded = recorded_actual_gbp(row)
    return MonthlyBudgetLine(
        id=row.id,
        scope=FinanceScope(row.scope),
        month=row.month,
        category=row.category,
        budgeted_gbp=row.budgeted_gbp,
        actual_gbp=recorded,
        remaining_gbp=round(row.budgeted_gbp - recorded, 2) if recorded is not None else None,
        actual_recorded=recorded is not None,
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
            if body.actual_gbp is not None:
                existing.actual_gbp = body.actual_gbp
                if (existing.notes or "").strip() in UNRECORDED_ACTUAL_NOTES:
                    existing.notes = body.notes or ""
                elif body.notes:
                    existing.notes = body.notes
            elif body.notes:
                existing.notes = body.notes
            existing.updated_at = now
            row = existing
        else:
            recorded = body.actual_gbp is not None
            row = MonthlyBudgetRow(
                scope=body.scope.value,
                month=body.month,
                category=body.category,
                budgeted_gbp=body.budgeted_gbp,
                actual_gbp=body.actual_gbp if recorded else 0.0,
                notes=body.notes or ("" if recorded else "Unrecorded actual"),
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)

    async def upsert_lines(
        self,
        db: AsyncSession,
        bodies: list[MonthlyBudgetLineCreate],
    ) -> list[MonthlyBudgetLine]:
        saved: list[MonthlyBudgetLine] = []
        for body in bodies:
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
                if body.actual_gbp is not None:
                    existing.actual_gbp = body.actual_gbp
                    if (existing.notes or "").strip() in UNRECORDED_ACTUAL_NOTES:
                        existing.notes = body.notes or ""
                    elif body.notes:
                        existing.notes = body.notes
                elif body.notes:
                    existing.notes = body.notes
                existing.updated_at = now
                row = existing
            else:
                recorded = body.actual_gbp is not None
                row = MonthlyBudgetRow(
                    scope=body.scope.value,
                    month=body.month,
                    category=body.category,
                    budgeted_gbp=body.budgeted_gbp,
                    actual_gbp=body.actual_gbp if recorded else 0.0,
                    notes=body.notes or ("" if recorded else "Unrecorded actual"),
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
            await db.flush()
            saved.append(_to_schema(row))
        await db.commit()
        return saved

    async def update_line(
        self,
        db: AsyncSession,
        line_id: int,
        body: MonthlyBudgetLineUpdate,
    ) -> MonthlyBudgetLine | None:
        row = await db.get(MonthlyBudgetRow, line_id)
        if row is None:
            return None
        updates = body.model_dump(exclude_unset=True)
        if "actual_gbp" in updates and updates["actual_gbp"] is None:
            updates.pop("actual_gbp")
        if "actual_gbp" in updates:
            if (row.notes or "").strip() in UNRECORDED_ACTUAL_NOTES:
                updates.setdefault("notes", "")
        for field, value in updates.items():
            setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)

    async def delete_line(self, db: AsyncSession, line_id: int) -> bool:
        row = await db.get(MonthlyBudgetRow, line_id)
        if row is None:
            return False
        await db.delete(row)
        await db.commit()
        return True

    async def apply_plan_amounts(
        self,
        db: AsyncSession,
        *,
        month: str,
        lines: list[tuple[str, str, float]],
        commit: bool = True,
    ) -> None:
        """Set budgeted amounts from a plan without wiping recorded actuals."""
        now = datetime.now(timezone.utc)
        for scope, category, amount in lines:
            existing = await db.scalar(
                select(MonthlyBudgetRow).where(
                    MonthlyBudgetRow.scope == scope,
                    MonthlyBudgetRow.month == month,
                    MonthlyBudgetRow.category == category,
                )
            )
            if existing:
                existing.budgeted_gbp = amount
                existing.updated_at = now
            else:
                db.add(
                    MonthlyBudgetRow(
                        scope=scope,
                        month=month,
                        category=category,
                        budgeted_gbp=amount,
                        actual_gbp=0.0,
                        notes="From active budget",
                        created_at=now,
                        updated_at=now,
                    )
                )
        if commit:
            await db.commit()

    async def ensure_starter_lines(
        self,
        db: AsyncSession,
        *,
        month: str,
        scope: FinanceScope,
        plan_amounts: dict[str, float] | None = None,
    ) -> list[MonthlyBudgetLine]:
        existing = await self.list_budget(db, month=month, scope=scope)
        if existing:
            return existing
        categories = list(
            PERSONAL_CATEGORIES if scope == FinanceScope.PERSONAL else BUSINESS_CATEGORIES
        )
        amounts = plan_amounts or {}
        extras = [name for name in amounts if name not in categories]
        now = datetime.now(timezone.utc)
        for category in [*categories, *extras]:
            db.add(
                MonthlyBudgetRow(
                    scope=scope.value,
                    month=month,
                    category=category,
                    budgeted_gbp=float(amounts.get(category, 0.0)),
                    actual_gbp=0.0,
                    notes="Starter category",
                    created_at=now,
                    updated_at=now,
                )
            )
        await db.commit()
        return await self.list_budget(db, month=month, scope=scope)

    async def month_totals(self, db: AsyncSession, month: str) -> tuple[float, float]:
        rows = await self.list_budget(db, month=month)
        budgeted = sum(row.budgeted_gbp for row in rows)
        actual = sum(row.actual_gbp or 0.0 for row in rows if row.actual_recorded)
        return round(budgeted, 2), round(actual, 2)

    async def month_flow(self, db: AsyncSession, month: str) -> tuple[float, float]:
        """Income and spending the monthly-flow resolver can use as a last resort."""
        budgeted, actual = await self.month_totals(db, month)
        spending = actual if actual > 0 else budgeted
        income = 0.0
        try:
            from app.services.finance.finance_budget_plan_service import (
                finance_budget_plan_service,
            )

            plan = await finance_budget_plan_service.get_active(db)
            if plan is not None:
                income = plan.income_gbp
                if spending <= 0:
                    spending = plan.totals.total_spending_gbp
        except Exception:
            pass
        return round(income, 2), round(spending, 2)


finance_budget_service = FinanceBudgetService()
