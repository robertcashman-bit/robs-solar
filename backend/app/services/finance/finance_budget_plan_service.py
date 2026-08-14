"""Persisted budget plans — gather real records, then call budget_engine."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CashflowForecastRow,
    FinanceBudgetItemRow,
    FinanceBudgetPlanRow,
    FinanceTransactionRow,
)
from app.schemas.finance import (
    ActiveBudgetSummary,
    BudgetCashContext,
    BudgetDuplicateRequest,
    BudgetItemKindType,
    BudgetMissingInput,
    BudgetPlan,
    BudgetPlanCreate,
    BudgetPlanItem,
    BudgetPlanItemWrite,
    BudgetPlanSummary,
    BudgetPlanUpdate,
    BudgetStrategyType,
    BudgetSuggestion,
    BudgetSuggestionsResponse,
    BudgetTaxContext,
    BudgetTotals,
    BudgetVarianceLine,
    BudgetVarianceResponse,
    BudgetViewType,
    FinanceAccountType,
    FinanceScope,
)
from app.services.finance.budget_engine import (
    BudgetDraft,
    BudgetDraftItem,
    BusinessSnapshotInput,
    CashflowRecordInput,
    DebtRecordInput,
    PersonalSnapshotInput,
    TransactionAverageInput,
    apply_overrides,
    calculate_budget_inputs,
    calculate_budget_totals,
    calculate_budget_variance,
    generate_all_suggestions,
    generate_suggested_budget,
    item_key,
    merge_refresh_preserving_overrides,
    money,
    recommended_strategy,
    to_monthly_amount,
)
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service
from app.services.finance.quickfile_reports_service import quickfile_reports_service

DEBT_ACCOUNT_TYPES = {
    FinanceAccountType.CREDIT_CARD,
    FinanceAccountType.LOAN,
    FinanceAccountType.MORTGAGE,
    FinanceAccountType.CAPITAL_ON_TAP,
    FinanceAccountType.CREDITORS,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _totals_from_engine(totals) -> BudgetTotals:
    return BudgetTotals(**totals.to_dict())


def _missing_from_engine(missing) -> list[BudgetMissingInput]:
    return [
        BudgetMissingInput(
            code=item.code,
            message=item.message,
            record_href=item.record_href,
            source_record_type=item.source_record_type,
            source_record_id=item.source_record_id,
            category=item.category,
        )
        for item in missing
    ]


def _item_from_draft(item: BudgetDraftItem, item_id: int | None = None) -> BudgetPlanItem:
    return BudgetPlanItem(
        id=item_id,
        key=item.key,
        scope=FinanceScope(item.scope),
        kind=BudgetItemKindType(item.kind),
        category=item.category,
        amount_gbp=item.amount_gbp,
        source=item.source,
        source_label=item.source_label,
        source_record_type=item.source_record_type,
        source_record_id=item.source_record_id,
        is_generated=item.is_generated,
        is_user_override=item.is_user_override,
        is_transfer=item.is_transfer,
        is_missing=item.is_missing,
        notes=item.notes,
        record_href=item.record_href,
    )


def _draft_from_row(row: FinanceBudgetItemRow) -> BudgetDraftItem:
    return BudgetDraftItem(
        key=row.item_key
        or item_key(
            scope=row.scope,
            kind=row.kind,
            source_record_type=row.source_record_type,
            source_record_id=row.source_record_id,
            slug=row.category,
        ),
        scope=row.scope,
        kind=row.kind,
        category=row.category,
        amount_gbp=row.amount_gbp,
        source=row.source,
        source_label=row.source_label or row.source,
        source_record_type=row.source_record_type,
        source_record_id=row.source_record_id,
        is_generated=row.is_generated,
        is_user_override=row.is_user_override,
        is_transfer=row.is_transfer,
        is_missing=row.is_missing or row.amount_gbp is None,
        notes=row.notes,
        record_href=row.record_href,
    )


def _write_to_draft(body: BudgetPlanItemWrite) -> BudgetDraftItem:
    is_missing = body.is_missing or body.amount_gbp is None
    key = body.key or item_key(
        scope=body.scope.value,
        kind=body.kind.value,
        source_record_type=body.source_record_type,
        source_record_id=body.source_record_id,
        slug=body.category,
    )
    return BudgetDraftItem(
        key=key,
        scope=body.scope.value,
        kind=body.kind.value,
        category=body.category,
        amount_gbp=None if is_missing else body.amount_gbp,
        source=body.source,
        source_label=body.source_label or body.source,
        source_record_type=body.source_record_type,
        source_record_id=body.source_record_id,
        is_generated=body.is_generated,
        is_user_override=body.is_user_override,
        is_transfer=body.is_transfer,
        is_missing=is_missing,
        notes=body.notes,
        record_href=body.record_href,
    )


def _tax_schema(tax) -> BudgetTaxContext:
    return BudgetTaxContext(
        vat_reserved_gbp=tax.vat_reserved_gbp,
        corp_tax_reserved_gbp=tax.corp_tax_reserved_gbp,
        vat_due_gbp=tax.vat_due_gbp,
        notes=list(tax.notes),
    )


def _cash_schema(cash) -> BudgetCashContext:
    return BudgetCashContext(
        savings_balance_gbp=cash.savings_balance_gbp,
        savings_accounts_found=cash.savings_accounts_found,
    )


def _active_summary(plan: BudgetPlan) -> ActiveBudgetSummary:
    totals = plan.totals_consolidated
    return ActiveBudgetSummary(
        id=plan.id,
        name=plan.name,
        strategy=plan.strategy,
        period=plan.period,
        income_gbp=totals.income_gbp,
        allocated_gbp=totals.allocated_gbp,
        debt_overpayment_gbp=totals.debt_overpayment_gbp,
        surplus_gbp=totals.surplus_gbp,
        has_missing_inputs=totals.has_missing_inputs,
        is_deficit=totals.is_deficit,
        income_complete=totals.income_complete,
        incomplete_reason=totals.incomplete_reason,
        totals=totals,
    )


def _summary_from_plan(plan: BudgetPlan) -> BudgetPlanSummary:
    totals = plan.totals_consolidated
    return BudgetPlanSummary(
        id=plan.id,
        name=plan.name,
        strategy=plan.strategy,
        period=plan.period,
        is_active=plan.is_active,
        is_archived=plan.is_archived,
        source_stale=plan.source_stale,
        has_missing_inputs=totals.has_missing_inputs,
        is_deficit=totals.is_deficit,
        income_gbp=totals.income_gbp,
        allocated_gbp=totals.allocated_gbp,
        surplus_gbp=totals.surplus_gbp,
        updated_at=plan.updated_at,
    )


class FinanceBudgetPlanService:
    async def _gather_inputs(self, db: AsyncSession):
        accounts = await finance_accounts_service.list_accounts(db)
        liabilities = await finance_liabilities_service.list_liabilities(db, active_only=False)
        personal_snap = await finance_overview_service.latest_personal_snapshot(db)
        business_snap = await finance_overview_service.latest_business_snapshot(db)
        qf_reports = await quickfile_reports_service.get_stored_reports(db)

        personal = None
        if personal_snap is not None:
            personal = PersonalSnapshotInput(
                exists=True,
                snapshot_id=personal_snap.id,
                monthly_income_gbp=personal_snap.monthly_income_gbp,
                household_bills_gbp=personal_snap.household_bills_gbp,
                monthly_spending_gbp=personal_snap.monthly_spending_gbp,
                debt_repayments_gbp=personal_snap.debt_repayments_gbp,
            )
        else:
            personal = PersonalSnapshotInput(exists=False)

        business = BusinessSnapshotInput(exists=False)
        if qf_reports and qf_reports.profit_and_loss_month:
            pl = qf_reports.profit_and_loss_month
            vat_reserve = business_snap.vat_reserve_gbp if business_snap else 0.0
            corp_reserve = business_snap.corp_tax_reserve_gbp if business_snap else 0.0
            business = BusinessSnapshotInput(
                exists=True,
                source="quickfile",
                snapshot_id=business_snap.id if business_snap else None,
                turnover_gbp=pl.turnover_gbp,
                expenses_gbp=pl.expenses_gbp,
                vat_reserve_gbp=vat_reserve,
                corp_tax_reserve_gbp=corp_reserve,
            )
        elif business_snap is not None:
            business = BusinessSnapshotInput(
                exists=True,
                source="snapshot",
                snapshot_id=business_snap.id,
                turnover_gbp=business_snap.turnover_gbp,
                expenses_gbp=business_snap.expenses_gbp,
                vat_reserve_gbp=business_snap.vat_reserve_gbp,
                corp_tax_reserve_gbp=business_snap.corp_tax_reserve_gbp,
            )

        linked_account_ids = {
            debt.account_id for debt in liabilities if debt.account_id is not None
        }
        debts: list[DebtRecordInput] = []
        skipped_inactive: list[DebtRecordInput] = []
        for debt in liabilities:
            min_payment: float | None = debt.minimum_payment_gbp
            if debt.balance_gbp > 0 and (min_payment is None or min_payment == 0):
                min_payment = None
            record = DebtRecordInput(
                id=debt.id,
                scope=debt.scope.value,
                name=debt.name,
                debt_type=debt.debt_type.value,
                balance_gbp=debt.balance_gbp,
                interest_rate_pct=debt.interest_rate_pct,
                minimum_payment_gbp=min_payment,
                overpayment_gbp=debt.overpayment_gbp,
                account_id=debt.account_id,
                origin="liability",
            )
            if not debt.is_active:
                if debt.balance_gbp > 0:
                    skipped_inactive.append(record)
                continue
            if debt.balance_gbp <= 0:
                continue
            debts.append(record)

        for account in accounts:
            if not account.is_active:
                continue
            if account.account_type not in DEBT_ACCOUNT_TYPES:
                continue
            if account.id in linked_account_ids:
                continue
            if account.balance_gbp <= 0:
                continue
            min_payment = account.minimum_payment_gbp
            if min_payment is None or min_payment == 0:
                min_payment = None
            debts.append(
                DebtRecordInput(
                    id=account.id,
                    scope=account.scope.value,
                    name=account.name,
                    debt_type=account.account_type.value,
                    balance_gbp=account.balance_gbp,
                    interest_rate_pct=account.interest_rate_pct or 0.0,
                    minimum_payment_gbp=min_payment,
                    overpayment_gbp=0.0,
                    account_id=account.id,
                    origin="account",
                )
            )

        cashflow_rows = list(
            (
                await db.scalars(
                    select(CashflowForecastRow).where(CashflowForecastRow.is_confirmed.is_(True))
                )
            ).all()
        )
        confirmed = [
            CashflowRecordInput(
                id=row.id,
                scope=row.scope,
                entry_type=row.entry_type,
                label=row.label,
                amount_gbp=row.amount_gbp,
                is_confirmed=True,
            )
            for row in cashflow_rows
        ]

        averages = await self._transaction_averages(db, accounts)
        savings_accounts = [
            a
            for a in accounts
            if a.is_active and a.account_type == FinanceAccountType.SAVINGS
        ]
        savings_found = bool(savings_accounts)
        savings_balance = sum(a.balance_gbp for a in savings_accounts) if savings_found else None

        vat_accounts = sum(
            a.balance_gbp
            for a in accounts
            if a.is_active and a.account_type == FinanceAccountType.VAT_RESERVE
        )
        corp_accounts = sum(
            a.balance_gbp
            for a in accounts
            if a.is_active and a.account_type == FinanceAccountType.CORP_TAX_RESERVE
        )
        vat_due = None
        if qf_reports and qf_reports.balance_sheet and qf_reports.balance_sheet.vat_liability_gbp:
            vat_due = qf_reports.balance_sheet.vat_liability_gbp

        return calculate_budget_inputs(
            personal=personal,
            business=business,
            debts=debts,
            confirmed_cashflow=confirmed,
            transaction_averages=averages,
            savings_balance_gbp=savings_balance,
            savings_accounts_found=savings_found,
            vat_due_gbp=vat_due,
            account_vat_reserve_gbp=vat_accounts,
            account_corp_tax_reserve_gbp=corp_accounts,
            skipped_inactive_debts=skipped_inactive,
        )

    async def _transaction_averages(
        self,
        db: AsyncSession,
        accounts,
    ) -> list[TransactionAverageInput]:
        rows = list((await db.scalars(select(FinanceTransactionRow))).all())
        if not rows:
            return []
        scope_by_account = {a.id: a.scope.value for a in accounts}
        by_month_cat: dict[tuple[str, str, str], Decimal] = defaultdict(lambda: Decimal("0"))
        months: set[str] = set()
        for row in rows:
            if row.amount_gbp >= 0:
                continue
            month = row.transaction_date[:7]
            months.add(month)
            category = (row.category or "").strip() or "Uncategorised"
            scope = scope_by_account.get(row.account_id, "personal")
            by_month_cat[(scope, category, month)] += Decimal(str(abs(row.amount_gbp)))
        if not months:
            return []
        month_count = len(months)
        totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
        for (scope, category, _month), amount in by_month_cat.items():
            totals[(scope, category)] += amount
        return [
            TransactionAverageInput(
                category=category,
                monthly_average_gbp=money(total / Decimal(month_count)),
                scope=scope,
            )
            for (scope, category), total in totals.items()
            if total > 0
        ]

    def _suggestion_from_draft(self, draft: BudgetDraft) -> BudgetSuggestion:
        return BudgetSuggestion(
            strategy=BudgetStrategyType(draft.strategy),
            name=draft.name,
            recommended=draft.recommended,
            items=[_item_from_draft(item) for item in draft.items],
            missing=_missing_from_engine(draft.missing),
            source_notes=list(draft.notes),
            tax=_tax_schema(draft.tax),
            cash=_cash_schema(draft.cash),
            fingerprint=draft.fingerprint,
            totals_personal=_totals_from_engine(draft.totals_personal),
            totals_business=_totals_from_engine(draft.totals_business),
            totals_consolidated=_totals_from_engine(draft.totals_consolidated),
        )

    async def _items_for_plan(
        self, db: AsyncSession, plan_id: int
    ) -> list[FinanceBudgetItemRow]:
        rows = await db.scalars(
            select(FinanceBudgetItemRow)
            .where(FinanceBudgetItemRow.budget_id == plan_id)
            .order_by(FinanceBudgetItemRow.id)
        )
        return list(rows.all())

    async def _plan_from_row(
        self,
        db: AsyncSession,
        row: FinanceBudgetPlanRow,
        *,
        current_fingerprint: str | None = None,
        live_missing=None,
        live_notes=None,
        live_tax=None,
        live_cash=None,
    ) -> BudgetPlan:
        item_rows = await self._items_for_plan(db, row.id)
        drafts = [_draft_from_row(item) for item in item_rows]
        items = [
            _item_from_draft(draft, item_id=item_row.id)
            for draft, item_row in zip(drafts, item_rows)
        ]
        stale = bool(
            current_fingerprint
            and row.source_fingerprint
            and current_fingerprint != row.source_fingerprint
        )
        return BudgetPlan(
            id=row.id,
            name=row.name,
            strategy=BudgetStrategyType(row.strategy),
            period=row.period,
            is_active=row.is_active,
            is_archived=row.is_archived,
            source_fingerprint=row.source_fingerprint,
            source_stale=stale,
            notes=row.notes,
            items=items,
            missing=_missing_from_engine(live_missing or []),
            source_notes=list(live_notes or []),
            tax=_tax_schema(live_tax) if live_tax else BudgetTaxContext(),
            cash=_cash_schema(live_cash) if live_cash else BudgetCashContext(),
            totals_personal=_totals_from_engine(calculate_budget_totals(drafts, "personal")),
            totals_business=_totals_from_engine(calculate_budget_totals(drafts, "business")),
            totals_consolidated=_totals_from_engine(
                calculate_budget_totals(drafts, "consolidated")
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _replace_items(
        self,
        db: AsyncSession,
        plan_id: int,
        items: list[BudgetDraftItem],
    ) -> None:
        existing = await self._items_for_plan(db, plan_id)
        for row in existing:
            await db.delete(row)
        now = _now()
        for item in items:
            db.add(
                FinanceBudgetItemRow(
                    budget_id=plan_id,
                    item_key=item.key,
                    scope=item.scope,
                    kind=item.kind,
                    category=item.category,
                    amount_gbp=item.amount_gbp,
                    source=item.source,
                    source_label=item.source_label,
                    source_record_type=item.source_record_type,
                    source_record_id=item.source_record_id,
                    is_generated=item.is_generated,
                    is_user_override=item.is_user_override,
                    is_transfer=item.is_transfer,
                    is_missing=item.is_missing or item.amount_gbp is None,
                    notes=item.notes,
                    record_href=item.record_href,
                    created_at=now,
                    updated_at=now,
                )
            )

    async def _clear_active(self, db: AsyncSession) -> None:
        rows = await db.scalars(
            select(FinanceBudgetPlanRow).where(FinanceBudgetPlanRow.is_active.is_(True))
        )
        for row in rows.all():
            row.is_active = False
            row.updated_at = _now()

    async def suggestions(self, db: AsyncSession) -> BudgetSuggestionsResponse:
        inputs = await self._gather_inputs(db)
        drafts = generate_all_suggestions(inputs)
        saved = await self.list_plans(db, include_archived=False, inputs=inputs)
        active_id = next((p.id for p in saved if p.is_active), None)
        return BudgetSuggestionsResponse(
            recommended_strategy=BudgetStrategyType(recommended_strategy(inputs)),
            fingerprint=inputs.fingerprint,
            missing=_missing_from_engine(inputs.missing),
            source_notes=list(inputs.notes),
            tax=_tax_schema(inputs.tax),
            cash=_cash_schema(inputs.cash),
            suggestions=[self._suggestion_from_draft(d) for d in drafts],
            saved_plans=saved,
            active_plan_id=active_id,
        )

    async def list_plans(
        self,
        db: AsyncSession,
        *,
        include_archived: bool = False,
        inputs=None,
    ) -> list[BudgetPlanSummary]:
        stmt = select(FinanceBudgetPlanRow).order_by(FinanceBudgetPlanRow.updated_at.desc())
        if not include_archived:
            stmt = stmt.where(FinanceBudgetPlanRow.is_archived.is_(False))
        rows = list((await db.scalars(stmt)).all())
        if inputs is None and rows:
            inputs = await self._gather_inputs(db)
        fingerprint = inputs.fingerprint if inputs else ""
        summaries: list[BudgetPlanSummary] = []
        for row in rows:
            plan = await self._plan_from_row(
                db,
                row,
                current_fingerprint=fingerprint,
                live_missing=inputs.missing if inputs else None,
                live_notes=inputs.notes if inputs else None,
                live_tax=inputs.tax if inputs else None,
                live_cash=inputs.cash if inputs else None,
            )
            summaries.append(_summary_from_plan(plan))
        return summaries

    async def get_plan(self, db: AsyncSession, plan_id: int) -> BudgetPlan | None:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None:
            return None
        inputs = await self._gather_inputs(db)
        return await self._plan_from_row(
            db,
            row,
            current_fingerprint=inputs.fingerprint,
            live_missing=inputs.missing,
            live_notes=inputs.notes,
            live_tax=inputs.tax,
            live_cash=inputs.cash,
        )

    async def get_active_plan(self, db: AsyncSession) -> BudgetPlan | None:
        row = await db.scalar(
            select(FinanceBudgetPlanRow).where(
                FinanceBudgetPlanRow.is_active.is_(True),
                FinanceBudgetPlanRow.is_archived.is_(False),
            )
        )
        if row is None:
            return None
        return await self.get_plan(db, row.id)

    async def get_active_summary(self, db: AsyncSession) -> ActiveBudgetSummary | None:
        plan = await self.get_active_plan(db)
        if plan is None:
            return None
        return _active_summary(plan)

    async def create_plan(self, db: AsyncSession, body: BudgetPlanCreate) -> BudgetPlan:
        now = _now()
        if body.activate:
            await self._clear_active(db)
        drafts = [_write_to_draft(item) for item in body.items]
        row = FinanceBudgetPlanRow(
            name=body.name.strip(),
            strategy=body.strategy.value,
            period=body.period or "monthly",
            is_active=body.activate,
            is_archived=False,
            source_fingerprint=body.source_fingerprint,
            notes=body.notes,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        await self._replace_items(db, row.id, drafts)
        await db.commit()
        await db.refresh(row)
        plan = await self.get_plan(db, row.id)
        assert plan is not None
        return plan

    async def update_plan(
        self, db: AsyncSession, plan_id: int, body: BudgetPlanUpdate
    ) -> BudgetPlan | None:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None:
            return None
        if body.name is not None:
            row.name = body.name.strip()
        if body.strategy is not None:
            row.strategy = body.strategy.value
        if body.notes is not None:
            row.notes = body.notes
        if body.source_fingerprint is not None:
            row.source_fingerprint = body.source_fingerprint
        if body.items is not None:
            drafts = [_write_to_draft(item) for item in body.items]
            await self._replace_items(db, row.id, drafts)
        row.updated_at = _now()
        await db.commit()
        return await self.get_plan(db, row.id)

    async def activate_plan(self, db: AsyncSession, plan_id: int) -> BudgetPlan | None:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None or row.is_archived:
            return None
        await self._clear_active(db)
        row.is_active = True
        row.updated_at = _now()
        await db.commit()
        return await self.get_plan(db, row.id)

    async def deactivate_plan(self, db: AsyncSession, plan_id: int) -> BudgetPlan | None:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None:
            return None
        row.is_active = False
        row.updated_at = _now()
        await db.commit()
        return await self.get_plan(db, row.id)

    async def duplicate_plan(
        self, db: AsyncSession, plan_id: int, body: BudgetDuplicateRequest | None = None
    ) -> BudgetPlan | None:
        source = await db.get(FinanceBudgetPlanRow, plan_id)
        if source is None:
            return None
        items = [_draft_from_row(row) for row in await self._items_for_plan(db, plan_id)]
        name = (body.name.strip() if body and body.name else f"{source.name} copy")
        now = _now()
        row = FinanceBudgetPlanRow(
            name=name,
            strategy="custom",
            period=source.period,
            is_active=False,
            is_archived=False,
            source_fingerprint=source.source_fingerprint,
            notes=source.notes,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        await self._replace_items(db, row.id, items)
        await db.commit()
        await db.refresh(row)
        plan = await self.get_plan(db, row.id)
        assert plan is not None
        return plan

    async def reset_plan(self, db: AsyncSession, plan_id: int) -> BudgetPlan | None:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None:
            return None
        inputs = await self._gather_inputs(db)
        strategy = row.strategy if row.strategy != "custom" else "balanced"
        draft = generate_suggested_budget(inputs, strategy)  # type: ignore[arg-type]
        await self._replace_items(db, row.id, draft.items)
        row.source_fingerprint = inputs.fingerprint
        row.updated_at = _now()
        await db.commit()
        return await self.get_plan(db, row.id)

    async def refresh_plan(self, db: AsyncSession, plan_id: int) -> BudgetPlan | None:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None:
            return None
        previous = [_draft_from_row(item) for item in await self._items_for_plan(db, plan_id)]
        inputs = await self._gather_inputs(db)
        strategy = row.strategy if row.strategy != "custom" else "balanced"
        draft = generate_suggested_budget(inputs, strategy)  # type: ignore[arg-type]
        merged = merge_refresh_preserving_overrides(previous, draft.items)
        await self._replace_items(db, row.id, merged)
        row.source_fingerprint = inputs.fingerprint
        row.updated_at = _now()
        await db.commit()
        return await self.get_plan(db, row.id)

    async def archive_plan(self, db: AsyncSession, plan_id: int) -> BudgetPlan | None:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None:
            return None
        if row.is_active:
            raise ValueError(
                "Cannot remove the active budget. Activate another budget first, "
                "or deactivate this one and leave no active budget."
            )
        row.is_archived = True
        row.updated_at = _now()
        await db.commit()
        return await self.get_plan(db, row.id)

    async def delete_plan(self, db: AsyncSession, plan_id: int) -> bool:
        row = await db.get(FinanceBudgetPlanRow, plan_id)
        if row is None:
            return False
        if row.is_active:
            raise ValueError(
                "Cannot remove the active budget. Activate another budget first, "
                "or deactivate this one and leave no active budget."
            )
        for item in await self._items_for_plan(db, plan_id):
            await db.delete(item)
        await db.delete(row)
        await db.commit()
        return True

    async def variance_for_active(
        self,
        db: AsyncSession,
        *,
        month: str,
        view: BudgetViewType = BudgetViewType.CONSOLIDATED,
    ) -> BudgetVarianceResponse:
        plan = await self.get_active_plan(db)
        if plan is None:
            return BudgetVarianceResponse(
                available=False,
                reason="No active budget. Set an active budget to compare with actuals.",
                month=month,
                view=view.value,
            )
        return await self.variance_for_plan(db, plan, month=month, view=view)

    async def variance_for_plan(
        self,
        db: AsyncSession,
        plan: BudgetPlan,
        *,
        month: str,
        view: BudgetViewType = BudgetViewType.CONSOLIDATED,
    ) -> BudgetVarianceResponse:
        accounts = await finance_accounts_service.list_accounts(db, active_only=False)
        scope_by_account = {a.id: a.scope.value for a in accounts}
        start = f"{month}-01"
        last = monthrange(int(month[:4]), int(month[5:7]))[1]
        end = f"{month}-{last:02d}"
        rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.transaction_date >= start,
                        FinanceTransactionRow.transaction_date <= end,
                    )
                )
            ).all()
        )
        transactions = [
            {
                "transaction_date": row.transaction_date,
                "category": row.category,
                "amount_gbp": row.amount_gbp,
                "scope": scope_by_account.get(row.account_id),
            }
            for row in rows
        ]
        drafts = [
            BudgetDraftItem(
                key=item.key,
                scope=item.scope.value,
                kind=item.kind.value,
                category=item.category,
                amount_gbp=item.amount_gbp,
                source=item.source,
                source_label=item.source_label,
                source_record_type=item.source_record_type,
                source_record_id=item.source_record_id,
                is_generated=item.is_generated,
                is_user_override=item.is_user_override,
                is_transfer=item.is_transfer,
                is_missing=item.is_missing,
                notes=item.notes,
                record_href=item.record_href,
            )
            for item in plan.items
        ]
        result = calculate_budget_variance(
            drafts, transactions, month=month, view=view.value  # type: ignore[arg-type]
        )
        return BudgetVarianceResponse(
            available=result.available,
            reason=result.reason,
            month=result.month,
            view=result.view,
            lines=[BudgetVarianceLine(**line.__dict__) for line in result.lines],
            unbudgeted_actuals=[
                BudgetVarianceLine(**line.__dict__) for line in result.unbudgeted_actuals
            ],
            budgeted_total_gbp=result.budgeted_total_gbp,
            actual_total_gbp=result.actual_total_gbp,
        )

    def apply_item_overrides(
        self, items: list[BudgetDraftItem], overrides: dict[str, float | None]
    ) -> list[BudgetDraftItem]:
        return apply_overrides(items, overrides)

    def monthly_from_frequency(self, amount: float, frequency: str) -> float:
        return money(to_monthly_amount(amount, frequency))


finance_budget_plan_service = FinanceBudgetPlanService()
