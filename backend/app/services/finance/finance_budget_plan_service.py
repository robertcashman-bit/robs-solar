"""Named, editable budget plans and suggested-budget materialisation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceBudgetPlanLineRow, FinanceBudgetPlanRow, MonthlyBudgetRow
from app.schemas.finance import (
    ActiveBudgetSummary,
    BudgetCompareResponse,
    BudgetCompareRow,
    BudgetGap,
    BudgetPlan,
    BudgetPlanCreate,
    BudgetPlanFromSuggestion,
    BudgetPlanLine,
    BudgetPlanLineWrite,
    BudgetPlanUpdate,
    BudgetStyle,
    BudgetSuggestionsResponse,
    BudgetTotals,
    BudgetVsActualLine,
    BudgetVsActualResponse,
    FinanceScope,
    SuggestedBudgetOption,
)
from app.services.finance.budget_suggestion_service import (
    SuggestedBudget,
    suggest_budgets,
    summarise_lines,
)
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_calc import (
    SnapshotView,
    accounts_from_schema,
    business_snapshot_view,
    liabilities_from_schema,
    personal_snapshot_view,
    pick_open_banking_flow,
)
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service
from app.services.lunchflow_settings_service import lunchflow_settings_service
from app.services.truelayer_settings_service import truelayer_settings_service

logger = logging.getLogger(__name__)


def _line_schema(row: FinanceBudgetPlanLineRow) -> BudgetPlanLine:
    return BudgetPlanLine(
        id=row.id,
        scope=FinanceScope(row.scope),
        category=row.category,
        amount_gbp=row.amount_gbp,
        source=row.source,
        source_note=row.source_note,
        is_custom=row.is_custom,
        sort_order=row.sort_order,
        subcategory=getattr(row, "subcategory", "") or "",
        basis_json=getattr(row, "basis_json", "") or "{}",
        confidence=getattr(row, "confidence", "") or "",
        insufficient_data=bool(getattr(row, "insufficient_data", False)),
    )


def _totals(income: float, lines: list[BudgetPlanLine]) -> BudgetTotals:
    raw = summarise_lines(lines, income)
    return BudgetTotals(**raw)


def _plan_schema(row: FinanceBudgetPlanRow, lines: list[BudgetPlanLine]) -> BudgetPlan:
    return BudgetPlan(
        id=row.id,
        name=row.name,
        style=row.style,
        origin=row.origin,
        notes=row.notes,
        explanation=row.explanation,
        debt_intensity=row.debt_intensity,
        cash_buffer_target_gbp=row.cash_buffer_target_gbp,
        discretionary_gbp=row.discretionary_gbp,
        tax_reserve_gbp=row.tax_reserve_gbp,
        income_gbp=row.income_gbp,
        is_active=row.is_active,
        active_scope=getattr(row, "active_scope", "") or "",
        totals=_totals(row.income_gbp, lines),
        lines=sorted(lines, key=lambda item: (item.sort_order, item.category)),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class FinanceBudgetPlanService:
    async def _open_banking_flow(self, db: AsyncSession):
        lunchflow = await lunchflow_settings_service.get_monthly_flow(db)
        truelayer = await truelayer_settings_service.get_monthly_flow(db)
        return pick_open_banking_flow(lunchflow, truelayer)

    async def _personal_view(self, db: AsyncSession) -> SnapshotView | None:
        personal = personal_snapshot_view(
            await finance_overview_service.latest_personal_snapshot(db)
        )
        if personal is not None and personal.monthly_income_gbp > 0:
            return personal
        flow = await self._open_banking_flow(db)
        if not flow.has_values() or flow.income_gbp <= 0:
            return personal
        return SnapshotView(
            monthly_income_gbp=flow.income_gbp,
            monthly_spending_gbp=personal.monthly_spending_gbp if personal else 0.0,
            household_bills_gbp=personal.household_bills_gbp if personal else 0.0,
            debt_repayments_gbp=personal.debt_repayments_gbp if personal else 0.0,
        )

    async def _load_inputs(self, db: AsyncSession):
        accounts = await finance_accounts_service.list_accounts(db, refresh_live=False)
        liabilities = await finance_liabilities_service.list_liabilities(db)
        business = await finance_overview_service.latest_business_snapshot(db)
        return (
            accounts_from_schema(accounts),
            liabilities_from_schema(liabilities),
            await self._personal_view(db),
            business_snapshot_view(business),
        )

    async def _lines_for(self, db: AsyncSession, plan_id: int) -> list[BudgetPlanLine]:
        rows = await db.scalars(
            select(FinanceBudgetPlanLineRow)
            .where(FinanceBudgetPlanLineRow.plan_id == plan_id)
            .order_by(FinanceBudgetPlanLineRow.sort_order, FinanceBudgetPlanLineRow.id)
        )
        return [_line_schema(row) for row in rows.all()]

    async def _to_plan(self, db: AsyncSession, row: FinanceBudgetPlanRow) -> BudgetPlan:
        return _plan_schema(row, await self._lines_for(db, row.id))

    async def list_plans(self, db: AsyncSession) -> list[BudgetPlan]:
        rows = await db.scalars(
            select(FinanceBudgetPlanRow).order_by(
                FinanceBudgetPlanRow.is_active.desc(),
                FinanceBudgetPlanRow.updated_at.desc(),
            )
        )
        return [await self._to_plan(db, row) for row in rows.all()]

    async def get(self, db: AsyncSession, plan_id: int) -> BudgetPlan | None:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None:
            return None
        return await self._to_plan(db, row)

    async def get_active(self, db: AsyncSession, scope: str | None = None) -> BudgetPlan | None:
        rows = list(
            (
                await db.scalars(
                    select(FinanceBudgetPlanRow).where(FinanceBudgetPlanRow.is_active.is_(True))
                )
            ).all()
        )
        if not rows:
            return None
        if scope in {"personal", "business"}:
            scoped = next((item for item in rows if item.active_scope == scope), None)
            if scoped is not None:
                return await self._to_plan(db, scoped)
            combined = next((item for item in rows if not item.active_scope), None)
            if combined is not None:
                return await self._to_plan(db, combined)
            return None
        return await self._to_plan(db, rows[0])

    def summarise_active(self, plan: BudgetPlan) -> ActiveBudgetSummary:
        return ActiveBudgetSummary(
            id=plan.id,
            name=plan.name,
            style=plan.style,
            monthly_total_gbp=plan.totals.total_spending_gbp,
            surplus_gbp=plan.totals.surplus_gbp,
            debt_overpayment_gbp=plan.totals.debt_overpayment_gbp,
            buffer_target_gbp=plan.totals.buffer_gbp,
            income_gbp=plan.income_gbp,
        )

    async def get_active_summary(self, db: AsyncSession) -> ActiveBudgetSummary | None:
        plan = await self.get_active(db)
        if plan is None:
            return None
        return self.summarise_active(plan)

    async def suggestions(self, db: AsyncSession) -> BudgetSuggestionsResponse:
        from app.services.finance.finance_live_refresh_service import (
            finance_live_refresh_service,
        )

        # Balances only — never wait on a year of Lunch Flow transactions here.
        await finance_live_refresh_service.ensure_fresh(db, include_transactions=False)
        bundle = suggest_budgets(*(await self._load_inputs(db)))
        return BudgetSuggestionsResponse(
            income_gbp=bundle.income_gbp,
            personal_income_known=bundle.personal_income_known,
            default_style=bundle.default_style,
            gaps=[BudgetGap(field=g.field, message=g.message, href=g.href) for g in bundle.gaps],
            options=[_suggested_option(item) for item in bundle.options],
        )

    async def create(self, db: AsyncSession, body: BudgetPlanCreate) -> BudgetPlan:
        income = body.income_gbp
        if income is None:
            bundle = suggest_budgets(*(await self._load_inputs(db)))
            income = bundle.income_gbp
        now = datetime.now(timezone.utc)
        row = FinanceBudgetPlanRow(
            name=body.name,
            style=body.style.value,
            origin=body.origin,
            notes=body.notes,
            explanation=body.explanation,
            debt_intensity=body.debt_intensity,
            cash_buffer_target_gbp=body.cash_buffer_target_gbp,
            discretionary_gbp=body.discretionary_gbp,
            tax_reserve_gbp=body.tax_reserve_gbp,
            income_gbp=income,
            is_active=False,
            active_scope=body.active_scope or "",
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        await self._replace_lines(db, row.id, body.lines)
        await db.commit()
        await db.refresh(row)
        return await self._to_plan(db, row)

    async def create_from_suggestion(
        self,
        db: AsyncSession,
        body: BudgetPlanFromSuggestion,
    ) -> BudgetPlan:
        bundle = suggest_budgets(*(await self._load_inputs(db)))
        match = next((item for item in bundle.options if item.style == body.style.value), None)
        if match is None:
            raise ValueError("Unknown suggested budget style")
        plan = await self.create(
            db,
            BudgetPlanCreate(
                name=body.name or match.name,
                style=body.style,
                origin="suggested",
                notes=match.notes,
                explanation=match.explanation,
                debt_intensity=match.debt_intensity,
                cash_buffer_target_gbp=match.cash_buffer_target_gbp,
                discretionary_gbp=match.discretionary_gbp,
                tax_reserve_gbp=match.tax_reserve_gbp,
                income_gbp=match.income_gbp,
                lines=[
                    BudgetPlanLineWrite(
                        scope=FinanceScope(line.scope),
                        category=line.category,
                        amount_gbp=line.amount_gbp,
                        source=line.source,
                        source_note=line.source_note,
                        is_custom=line.is_custom,
                        sort_order=line.sort_order,
                    )
                    for line in match.lines
                ],
            ),
        )
        if body.activate:
            activated = await self.activate(db, plan.id)
            return activated or plan
        return plan

    async def ensure_active_from_suggestion(self, db: AsyncSession) -> BudgetPlan | None:
        """Create and activate the recommended live plan when none exists.

        Used after hosted SQLite resets. Does not invent income, bills, or
        actuals, and does not override a saved plan the user already has.
        """
        existing = await self.get_active(db)
        if existing is not None:
            return existing
        count = await db.scalar(select(func.count()).select_from(FinanceBudgetPlanRow))
        if count:
            return None
        inputs = await self._load_inputs(db)
        flow = await self._open_banking_flow(db)
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        current_business = business_snapshot_view(
            await finance_overview_service.business_snapshot_for_month(db, month)
        )
        live_income = flow.income_gbp > 0 or (
            current_business is not None and current_business.turnover_gbp > 0
        )
        if not live_income:
            return None
        bundle = suggest_budgets(*inputs)
        if bundle.income_gbp <= 0:
            return None
        try:
            style = BudgetStyle(bundle.default_style)
        except ValueError:
            style = BudgetStyle.BALANCED
        if style == BudgetStyle.CUSTOM:
            style = BudgetStyle.BALANCED
        try:
            return await self.create_from_suggestion(
                db,
                BudgetPlanFromSuggestion(style=style, activate=True),
            )
        except Exception:
            logger.warning("Could not create recommended budget from live data", exc_info=True)
            await db.rollback()
            return None

    async def update(
        self, db: AsyncSession, plan_id: int, body: BudgetPlanUpdate
    ) -> BudgetPlan | None:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None:
            return None
        data = body.model_dump(exclude_unset=True)
        lines = data.pop("lines", None)
        for field, value in data.items():
            setattr(row, field, value)
        if lines is not None:
            written = [
                BudgetPlanLineWrite(**item) if isinstance(item, dict) else item
                for item in lines
            ]
            await self._replace_lines(db, plan_id, written)
            current_lines = await self._lines_for(db, plan_id)
            totals = _totals(row.income_gbp, current_lines)
            row.cash_buffer_target_gbp = totals.buffer_gbp
            row.discretionary_gbp = totals.discretionary_gbp
            row.tax_reserve_gbp = totals.tax_reserve_gbp
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
        return await self._to_plan(db, row)

    async def duplicate(self, db: AsyncSession, plan_id: int) -> BudgetPlan | None:
        source = await self.get(db, plan_id)
        if source is None:
            return None
        return await self.create(
            db,
            BudgetPlanCreate(
                name=f"{source.name} copy",
                style=_safe_style(source.style),
                origin="user",
                notes=source.notes,
                explanation=source.explanation,
                debt_intensity=source.debt_intensity,
                cash_buffer_target_gbp=source.cash_buffer_target_gbp,
                discretionary_gbp=source.discretionary_gbp,
                tax_reserve_gbp=source.tax_reserve_gbp,
                income_gbp=source.income_gbp,
                lines=[
                    BudgetPlanLineWrite(
                        scope=line.scope,
                        category=line.category,
                        amount_gbp=line.amount_gbp,
                        source=line.source,
                        source_note=line.source_note,
                        is_custom=line.is_custom,
                        sort_order=line.sort_order,
                    )
                    for line in source.lines
                ],
            ),
        )

    async def activate(
        self, db: AsyncSession, plan_id: int, scope: str | None = None
    ) -> BudgetPlan | None:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None:
            return None
        target_scope = (scope or row.active_scope or "").strip()
        existing = await db.scalars(
            select(FinanceBudgetPlanRow).where(FinanceBudgetPlanRow.is_active.is_(True))
        )
        for item in existing.all():
            if item.id == row.id:
                continue
            if not target_scope or item.active_scope in {"", target_scope}:
                item.is_active = False
        row.is_active = True
        row.active_scope = target_scope
        row.updated_at = datetime.now(timezone.utc)
        plan = await self._to_plan(db, row)
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        from app.services.finance.finance_budget_service import finance_budget_service

        await finance_budget_service.apply_plan_amounts(
            db,
            month=month,
            lines=[
                (line.scope.value, line.category, line.amount_gbp) for line in plan.lines
            ],
            commit=False,
        )
        await db.commit()
        await db.refresh(row)
        return await self._to_plan(db, row)

    async def delete(self, db: AsyncSession, plan_id: int) -> bool:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None:
            return False
        lines = await db.scalars(
            select(FinanceBudgetPlanLineRow).where(FinanceBudgetPlanLineRow.plan_id == plan_id)
        )
        for line in lines.all():
            await db.delete(line)
        await db.delete(row)
        await db.commit()
        return True

    async def compare(self, db: AsyncSession) -> BudgetCompareResponse:
        plans = await self.list_plans(db)
        suggestions = await self.suggestions(db)
        income = suggestions.income_gbp
        rows: list[BudgetCompareRow] = []
        for option in suggestions.options:
            rows.append(
                BudgetCompareRow(
                    id=None,
                    key=option.style,
                    name=option.name,
                    style=option.style,
                    monthly_total_gbp=round(
                        option.committed_gbp
                        + option.discretionary_gbp
                        + option.debt_overpayment_gbp
                        + option.cash_buffer_target_gbp,
                        2,
                    ),
                    surplus_gbp=option.surplus_gbp,
                    debt_overpayment_gbp=option.debt_overpayment_gbp,
                    buffer_gbp=option.cash_buffer_target_gbp,
                    discretionary_gbp=option.discretionary_gbp,
                    tax_reserve_gbp=option.tax_reserve_gbp,
                    shortfall_gbp=option.shortfall_gbp,
                )
            )
        for plan in plans:
            rows.append(
                BudgetCompareRow(
                    id=plan.id,
                    key=f"plan-{plan.id}",
                    name=plan.name,
                    style=plan.style,
                    monthly_total_gbp=plan.totals.total_spending_gbp,
                    surplus_gbp=plan.totals.surplus_gbp,
                    debt_overpayment_gbp=plan.totals.debt_overpayment_gbp,
                    buffer_gbp=plan.totals.buffer_gbp,
                    discretionary_gbp=plan.totals.discretionary_gbp,
                    tax_reserve_gbp=plan.totals.tax_reserve_gbp,
                    shortfall_gbp=plan.totals.shortfall_gbp,
                    is_active=plan.is_active,
                )
            )
        return BudgetCompareResponse(rows=rows, income_gbp=income)

    async def vs_actual(
        self, db: AsyncSession, month: str, scope: str | None = None
    ) -> BudgetVsActualResponse:
        from app.db.models import FinanceTransactionRow
        from app.services.finance.finance_budget_service import recorded_actual_gbp
        from app.services.finance.money import from_pence

        plan = await self.get_active(db, scope=scope)
        actual_rows = await db.scalars(
            select(MonthlyBudgetRow).where(MonthlyBudgetRow.month == month)
        )
        actuals = list(actual_rows.all())
        if scope in {"personal", "business"}:
            actuals = [row for row in actuals if row.scope == scope]
        actual_map = {(row.scope, row.category.lower()): row for row in actuals}
        tx_rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.posted_on.startswith(month),
                        FinanceTransactionRow.is_deleted.is_(False),
                        FinanceTransactionRow.is_transfer.is_(False),
                    )
                )
            ).all()
        )
        if scope in {"personal", "business"}:
            tx_rows = [row for row in tx_rows if row.scope == scope]
        tx_totals: dict[tuple[str, str], int] = {}
        tx_counts: dict[tuple[str, str], int] = {}
        for row in tx_rows:
            key = (row.scope, (row.category or "Uncategorised").lower())
            tx_totals[key] = tx_totals.get(key, 0) + (
                -row.amount_pence if row.amount_pence < 0 else 0
            )
            if row.amount_pence > 0 and (row.category or "").lower() in {
                "salary",
                "income",
                "turnover",
            }:
                tx_totals[key] = tx_totals.get(key, 0) + row.amount_pence
            tx_counts[key] = tx_counts.get(key, 0) + 1

        def _resolve_actual(key: tuple[str, str], row: MonthlyBudgetRow | None):
            recorded = recorded_actual_gbp(row) if row is not None else None
            if recorded is not None:
                return recorded, "manual", 0
            if key in tx_totals and tx_counts.get(key, 0) > 0 and (row is not None or key[1] != ""):
                if key in tx_totals:
                    return from_pence(tx_totals[key]), "transactions", tx_counts[key]
            if key in tx_counts:
                return from_pence(tx_totals.get(key, 0)), "transactions", tx_counts[key]
            return None, "missing", 0
        lines: list[BudgetVsActualLine] = []
        used_keys: set[tuple[str, str]] = set()
        if plan:
            plan_lines = [
                line
                for line in plan.lines
                if scope not in {"personal", "business"} or line.scope.value == scope
            ]
            for line in plan_lines:
                key = (line.scope.value, line.category.lower())
                used_keys.add(key)
                row = actual_map.get(key)
                recorded, source, txn_count = _resolve_actual(key, row)
                percent = (
                    round((recorded / line.amount_gbp) * 100, 1)
                    if recorded is not None and line.amount_gbp
                    else None
                )
                remaining = (
                    round(line.amount_gbp - recorded, 2) if recorded is not None else None
                )
                lines.append(
                    BudgetVsActualLine(
                        scope=line.scope,
                        category=line.category,
                        budget_gbp=line.amount_gbp,
                        actual_gbp=recorded,
                        variance_gbp=remaining,
                        percent_used=percent,
                        missing_actual=recorded is None,
                        forecast_gbp=None,
                        remaining_gbp=remaining,
                        actual_source=source,
                        transaction_count=txn_count,
                    )
                )
        else:
            for row in actuals:
                key = (row.scope, row.category.lower())
                used_keys.add(key)
                recorded, source, txn_count = _resolve_actual(key, row)
                lines.append(
                    BudgetVsActualLine(
                        scope=FinanceScope(row.scope),
                        category=row.category,
                        budget_gbp=row.budgeted_gbp,
                        actual_gbp=recorded,
                        variance_gbp=(
                            round(row.budgeted_gbp - recorded, 2) if recorded is not None else None
                        ),
                        percent_used=(
                            round((recorded / row.budgeted_gbp) * 100, 1)
                            if recorded is not None and row.budgeted_gbp
                            else None
                        ),
                        missing_actual=recorded is None,
                        remaining_gbp=(
                            round(row.budgeted_gbp - recorded, 2) if recorded is not None else None
                        ),
                        actual_source=source,
                        transaction_count=txn_count,
                    )
                )
        unbudgeted: list[BudgetVsActualLine] = []
        if plan is not None:
            for row in actuals:
                key = (row.scope, row.category.lower())
                if key in used_keys:
                    continue
                recorded, source, txn_count = _resolve_actual(key, row)
                if recorded is None:
                    continue
                unbudgeted.append(
                    BudgetVsActualLine(
                        scope=FinanceScope(row.scope),
                        category=row.category,
                        budget_gbp=0,
                        actual_gbp=recorded,
                        variance_gbp=None,
                        percent_used=None,
                        missing_actual=False,
                        actual_source=source,
                        transaction_count=txn_count,
                    )
                )
            used_lower = {item[1] for item in used_keys}
            for key, total in tx_totals.items():
                if key in used_keys or key[1] in used_lower:
                    continue
                if key[1] == "uncategorised":
                    unbudgeted.append(
                        BudgetVsActualLine(
                            scope=FinanceScope(key[0]),
                            category="Uncategorised",
                            budget_gbp=0,
                            actual_gbp=from_pence(total),
                            variance_gbp=None,
                            percent_used=None,
                            missing_actual=False,
                            actual_source="transactions",
                            transaction_count=tx_counts.get(key, 0),
                        )
                    )
        recorded_actuals = [
            line.actual_gbp
            for line in lines
            if not line.missing_actual and line.actual_gbp is not None
        ]
        unbudgeted_actuals = [line.actual_gbp or 0 for line in unbudgeted]
        budgeted_total = round(sum(line.budget_gbp for line in lines), 2)
        actual_total = round(sum(recorded_actuals) + sum(unbudgeted_actuals), 2)
        has_actuals = bool(recorded_actuals or unbudgeted)
        available = plan is not None or bool(lines)
        reason = ""
        if not available:
            reason = (
                "No active budget. Set one on the Budget page to compare planned amounts "
                "with recorded actuals."
            )
        return BudgetVsActualResponse(
            month=month,
            plan_id=plan.id if plan else None,
            plan_name=plan.name if plan else None,
            lines=lines,
            unbudgeted_actuals=unbudgeted,
            has_actuals=has_actuals,
            available=available,
            reason=reason,
            budgeted_total_gbp=budgeted_total,
            actual_total_gbp=actual_total,
            variance_total_gbp=round(budgeted_total - actual_total, 2) if has_actuals else None,
        )

    async def _replace_lines(
        self,
        db: AsyncSession,
        plan_id: int,
        lines: list[BudgetPlanLineWrite],
    ) -> None:
        existing = await db.scalars(
            select(FinanceBudgetPlanLineRow).where(FinanceBudgetPlanLineRow.plan_id == plan_id)
        )
        for row in existing.all():
            await db.delete(row)
        await db.flush()
        for index, line in enumerate(lines):
            db.add(
                FinanceBudgetPlanLineRow(
                    plan_id=plan_id,
                    scope=line.scope.value,
                    category=line.category,
                    amount_gbp=line.amount_gbp,
                    source=line.source,
                    source_note=line.source_note,
                    is_custom=line.is_custom,
                    sort_order=line.sort_order or index * 10,
                    subcategory=getattr(line, "subcategory", "") or "",
                    basis_json=getattr(line, "basis_json", "") or "{}",
                    confidence=getattr(line, "confidence", "") or "",
                    insufficient_data=bool(getattr(line, "insufficient_data", False)),
                )
            )


def _suggested_option(item: SuggestedBudget) -> SuggestedBudgetOption:
    return SuggestedBudgetOption(
        style=item.style,
        name=item.name,
        explanation=item.explanation,
        debt_intensity=item.debt_intensity,
        cash_buffer_target_gbp=item.cash_buffer_target_gbp,
        discretionary_gbp=item.discretionary_gbp,
        tax_reserve_gbp=item.tax_reserve_gbp,
        income_gbp=item.income_gbp,
        committed_gbp=item.committed_gbp,
        debt_payment_gbp=item.debt_payment_gbp,
        debt_overpayment_gbp=item.debt_overpayment_gbp,
        surplus_gbp=item.surplus_gbp,
        shortfall_gbp=item.shortfall_gbp,
        recommended=item.recommended,
        incomplete=item.incomplete,
        notes=item.notes,
        gaps=[BudgetGap(field=g.field, message=g.message, href=g.href) for g in item.gaps],
        lines=[
            BudgetPlanLine(
                scope=FinanceScope(line.scope),
                category=line.category,
                amount_gbp=line.amount_gbp,
                source=line.source,
                source_note=line.source_note,
                is_custom=line.is_custom,
                sort_order=line.sort_order,
            )
            for line in item.lines
        ],
    )


def _safe_style(value: str) -> BudgetStyle:
    try:
        return BudgetStyle(value)
    except ValueError:
        return BudgetStyle.CUSTOM


finance_budget_plan_service = FinanceBudgetPlanService()
