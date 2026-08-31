"""Scoped personal/business cashflow plans with overdraft-limit breach flags."""

from __future__ import annotations

import logging
from calendar import month_name
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSettingRow
from app.schemas.finance import (
    CashflowPlanIssue,
    CashflowPlanMonth,
    DualCashflowPlansResponse,
    OverdraftLimitsResponse,
    ScopedCashflowPlan,
)
from app.services.finance.finance_calc import is_repayable_debt
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service
from app.services.finance.money import format_gbp

logger = logging.getLogger(__name__)

PERSONAL_OD_LIMIT_KEY = "finance.personal_overdraft_limit_gbp"
BUSINESS_OD_LIMIT_KEY = "finance.business_overdraft_limit_gbp"
DEFAULT_PERSONAL_OD_LIMIT_GBP = 3000.0
DEFAULT_BUSINESS_OD_LIMIT_GBP = 5000.0


def _month_keys(start: datetime, count: int) -> list[str]:
    year, month = start.year, start.month
    keys: list[str] = []
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return keys


def _month_label(key: str) -> str:
    year, month = key.split("-")
    return f"{month_name[int(month)]} {year}"


async def get_overdraft_limits(db: AsyncSession) -> OverdraftLimitsResponse:
    personal = await db.get(AppSettingRow, PERSONAL_OD_LIMIT_KEY)
    business = await db.get(AppSettingRow, BUSINESS_OD_LIMIT_KEY)
    return OverdraftLimitsResponse(
        personal_overdraft_limit_gbp=(
            float(personal.value)
            if personal is not None
            else DEFAULT_PERSONAL_OD_LIMIT_GBP
        ),
        business_overdraft_limit_gbp=(
            float(business.value)
            if business is not None
            else DEFAULT_BUSINESS_OD_LIMIT_GBP
        ),
    )


async def set_overdraft_limits(
    db: AsyncSession,
    *,
    personal_overdraft_limit_gbp: float | None = None,
    business_overdraft_limit_gbp: float | None = None,
) -> OverdraftLimitsResponse:
    if personal_overdraft_limit_gbp is not None:
        row = await db.get(AppSettingRow, PERSONAL_OD_LIMIT_KEY)
        value = f"{float(personal_overdraft_limit_gbp):.2f}"
        if row is None:
            db.add(AppSettingRow(key=PERSONAL_OD_LIMIT_KEY, value=value))
        else:
            row.value = value
    if business_overdraft_limit_gbp is not None:
        row = await db.get(AppSettingRow, BUSINESS_OD_LIMIT_KEY)
        value = f"{float(business_overdraft_limit_gbp):.2f}"
        if row is None:
            db.add(AppSettingRow(key=BUSINESS_OD_LIMIT_KEY, value=value))
        else:
            row.value = value
    await db.commit()
    return await get_overdraft_limits(db)


async def ensure_overdraft_limits() -> None:
    """Persist Robert's stated OD facilities once on the live database."""
    from app.db.session import SessionLocal
    from app.services.finance.finance_seed_service import is_live_finance_database

    if not is_live_finance_database():
        return
    async with SessionLocal() as db:
        personal = await db.get(AppSettingRow, PERSONAL_OD_LIMIT_KEY)
        business = await db.get(AppSettingRow, BUSINESS_OD_LIMIT_KEY)
        changed = False
        if personal is None:
            db.add(
                AppSettingRow(
                    key=PERSONAL_OD_LIMIT_KEY,
                    value=f"{DEFAULT_PERSONAL_OD_LIMIT_GBP:.2f}",
                )
            )
            changed = True
        if business is None:
            db.add(
                AppSettingRow(
                    key=BUSINESS_OD_LIMIT_KEY,
                    value=f"{DEFAULT_BUSINESS_OD_LIMIT_GBP:.2f}",
                )
            )
            changed = True
        if changed:
            await db.commit()
            logger.info(
                "Seeded overdraft limits personal=%.0f business=%.0f",
                DEFAULT_PERSONAL_OD_LIMIT_GBP,
                DEFAULT_BUSINESS_OD_LIMIT_GBP,
            )


def _income_looks_thin(income: float, budget_income: float | None) -> str | None:
    if income <= 0:
        return "No reliable month income recorded — cashflow plan incomplete."
    if budget_income and budget_income >= 1500 and income < budget_income * 0.4:
        return (
            f"Month income {format_gbp(income)} looks thin vs typical budget "
            f"income {format_gbp(budget_income)} — cashflow marked incomplete."
        )
    if income < 500:
        return (
            f"Month income {format_gbp(income)} looks implausibly low — "
            "cashflow marked incomplete (not treating this as full salary)."
        )
    return None


class CashflowPlanService:
    async def build_plans(
        self,
        db: AsyncSession,
        *,
        months: int = 3,
    ) -> DualCashflowPlansResponse:
        months = max(2, min(int(months), 6))
        limits = await get_overdraft_limits(db)
        overview = await finance_overview_service.get_overview(db)
        liabilities = await finance_liabilities_service.list_liabilities(
            db, sync_accounts=False
        )

        budget_income = float(getattr(overview.active_budget, "income_gbp", 0) or 0)
        budget_spend = float(
            getattr(overview.active_budget, "monthly_total_gbp", 0) or 0
        )
        # Prefer period ledger income when present; else overview monthly.
        personal_flow = overview.personal_period_flow
        income = float(overview.monthly_income_gbp or 0)
        if personal_flow and personal_flow.transaction_count > 0:
            income = float(personal_flow.income_gbp or 0)
        spending = float(overview.monthly_spending_gbp or 0)
        if personal_flow and personal_flow.transaction_count > 0:
            spending = float(personal_flow.spending_gbp or 0)
        if budget_spend > 0:
            # Typical budget (one-offs already excluded when plan was built).
            spending = budget_spend

        personal = self._scope_plan(
            scope="personal",
            starting_bank=float(overview.personal_bank_balance_gbp or 0),
            overdraft_drawn=float(overview.personal_overdraft_gbp or 0),
            overdraft_limit=limits.personal_overdraft_limit_gbp,
            income=income,
            spending=spending,
            budget_income=budget_income or None,
            liabilities=[
                d
                for d in liabilities
                if d.is_active
                and is_repayable_debt(d)
                and str(getattr(d.scope, "value", d.scope)) == "personal"
            ],
            months=months,
        )
        # Business: use period flow when available; otherwise 0 income with incomplete.
        business_flow = overview.business_period_flow
        biz_income = float(business_flow.income_gbp) if business_flow else 0.0
        biz_spend = float(business_flow.spending_gbp) if business_flow else 0.0
        if business_flow and business_flow.transaction_count <= 0:
            biz_income = 0.0
            biz_spend = 0.0
        business = self._scope_plan(
            scope="business",
            starting_bank=float(overview.business_bank_balance_gbp or 0),
            overdraft_drawn=float(overview.business_overdraft_gbp or 0),
            overdraft_limit=limits.business_overdraft_limit_gbp,
            income=biz_income,
            spending=biz_spend,
            budget_income=None,
            liabilities=[
                d
                for d in liabilities
                if d.is_active
                and is_repayable_debt(d)
                and str(getattr(d.scope, "value", d.scope)) == "business"
            ],
            months=months,
            allow_zero_income=True,
        )
        return DualCashflowPlansResponse(
            personal=personal,
            business=business,
            personal_overdraft_limit_gbp=limits.personal_overdraft_limit_gbp,
            business_overdraft_limit_gbp=limits.business_overdraft_limit_gbp,
        )

    def _scope_plan(
        self,
        *,
        scope: str,
        starting_bank: float,
        overdraft_drawn: float,
        overdraft_limit: float,
        income: float,
        spending: float,
        budget_income: float | None,
        liabilities: list,
        months: int,
        allow_zero_income: bool = False,
    ) -> ScopedCashflowPlan:
        issues: list[CashflowPlanIssue] = []
        card_warnings: list[str] = []
        floor = -abs(overdraft_limit)
        headroom = round(starting_bank - floor, 2)
        live_breach = starting_bank < floor - 0.005
        if live_breach:
            issues.append(
                CashflowPlanIssue(
                    severity="critical",
                    kind="live_overdraft_breach",
                    message=(
                        f"{scope.title()} bank is {format_gbp(starting_bank)}, "
                        f"already past the {format_gbp(overdraft_limit)} overdraft limit."
                    ),
                )
            )
        elif headroom < 500:
            issues.append(
                CashflowPlanIssue(
                    severity="warning",
                    kind="thin_overdraft_headroom",
                    message=(
                        f"{scope.title()} headroom vs {format_gbp(overdraft_limit)} "
                        f"overdraft is only {format_gbp(headroom)}."
                    ),
                )
            )

        incomplete_reason = ""
        if scope == "personal":
            thin = _income_looks_thin(income, budget_income)
            if thin:
                incomplete_reason = thin
                issues.append(
                    CashflowPlanIssue(
                        severity="warning",
                        kind="income_incomplete",
                        message=thin,
                    )
                )
        elif not allow_zero_income and income <= 0:
            incomplete_reason = "No business income in the selected period — plan incomplete."
            issues.append(
                CashflowPlanIssue(
                    severity="warning",
                    kind="income_incomplete",
                    message=incomplete_reason,
                )
            )
        elif allow_zero_income and income <= 0 and spending <= 0:
            incomplete_reason = (
                "Business cashflow has little stored income/spend for this window — "
                "treat projections as incomplete."
            )
            issues.append(
                CashflowPlanIssue(
                    severity="info",
                    kind="income_incomplete",
                    message=incomplete_reason,
                )
            )

        debt_payments = round(
            sum(
                max(float(d.minimum_payment_gbp or 0) + float(d.overpayment_gbp or 0), 0.0)
                for d in liabilities
            ),
            2,
        )
        for debt in liabilities:
            dtype = str(getattr(debt.debt_type, "value", debt.debt_type))
            if dtype not in {"credit_card", "business_loan"}:
                continue
            limit = getattr(debt, "credit_limit_gbp", None)
            if limit is None or float(limit) <= 0:
                card_warnings.append(f"{debt.name}: credit limit unknown")
                issues.append(
                    CashflowPlanIssue(
                        severity="info",
                        kind="card_limit_unknown",
                        message=f"{debt.name} has no credit limit recorded.",
                    )
                )
            elif float(debt.balance_gbp) > float(limit) + 0.005:
                card_warnings.append(
                    f"{debt.name}: balance {format_gbp(debt.balance_gbp)} "
                    f"exceeds limit {format_gbp(float(limit))}"
                )
                issues.append(
                    CashflowPlanIssue(
                        severity="critical",
                        kind="card_limit_breach",
                        message=(
                            f"{debt.name} balance {format_gbp(debt.balance_gbp)} "
                            f"is past the recorded limit {format_gbp(float(limit))}."
                        ),
                    )
                )

        # Net monthly movement excluding debt mins already inside spending when
        # spending comes from a budget that includes debt lines — still add mins
        # explicitly so debt service is visible on the plan.
        spend_ex_debt = max(spending - debt_payments, 0.0) if spending > 0 else 0.0
        if spending > 0 and debt_payments > spending:
            spend_ex_debt = spending  # budget already net of something odd

        now = datetime.now(timezone.utc)
        keys = _month_keys(now, months)
        plan_months: list[CashflowPlanMonth] = []
        opening = starting_bank
        # If income is incomplete, still project but flag — use 0 income rather
        # than inventing salary.
        use_income = 0.0 if incomplete_reason and scope == "personal" else income
        if incomplete_reason and scope == "personal":
            use_income = 0.0

        for index, key in enumerate(keys):
            notes: list[str] = []
            month_income = use_income
            if index == 0 and incomplete_reason and scope == "personal":
                notes.append("Income withheld from projection (looks incomplete)")
                month_income = 0.0
            closing = round(opening + month_income - spend_ex_debt - debt_payments, 2)
            breaches = closing < floor - 0.005
            if breaches:
                issues.append(
                    CashflowPlanIssue(
                        severity="critical",
                        kind="projected_overdraft_breach",
                        message=(
                            f"{scope.title()} projected {_month_label(key)} close "
                            f"{format_gbp(closing)} would breach the "
                            f"{format_gbp(overdraft_limit)} overdraft limit."
                        ),
                    )
                )
            plan_months.append(
                CashflowPlanMonth(
                    month=key,
                    label=_month_label(key),
                    opening_gbp=round(opening, 2),
                    income_gbp=round(month_income, 2),
                    spending_gbp=round(spend_ex_debt, 2),
                    debt_payments_gbp=debt_payments,
                    closing_gbp=closing,
                    overdraft_limit_gbp=overdraft_limit,
                    headroom_gbp=round(closing - floor, 2),
                    breaches_overdraft=breaches,
                    notes=notes,
                )
            )
            opening = closing

        # Dedupe issues by message
        seen: set[str] = set()
        unique_issues: list[CashflowPlanIssue] = []
        for issue in issues:
            if issue.message in seen:
                continue
            seen.add(issue.message)
            unique_issues.append(issue)

        return ScopedCashflowPlan(
            scope=scope,
            starting_bank_gbp=round(starting_bank, 2),
            overdraft_limit_gbp=overdraft_limit,
            overdraft_drawn_gbp=round(overdraft_drawn, 2),
            headroom_gbp=headroom,
            live_breach=live_breach,
            incomplete=bool(incomplete_reason),
            incomplete_reason=incomplete_reason,
            months=plan_months,
            issues=unique_issues,
            card_warnings=card_warnings,
        )


cashflow_plan_service = CashflowPlanService()
