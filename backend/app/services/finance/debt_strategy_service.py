"""Debt payoff strategy, priority scoring, and overpayment scenarios.

Plans are scoped: personal and business are separate avalanches. Director's
loan is never a repayable debt. Unknown APRs mark a plan incomplete — rates
are never invented.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from app.schemas.finance import (
    DebtAnalysisItem,
    DebtPayoffMilestone,
    DebtScenarioResult,
    DebtStrategyRecommendation,
    DualDebtStrategiesResponse,
    FinanceLiability,
)
from app.services.finance.finance_calc import is_repayable_debt, monthly_interest_gbp
from app.services.finance.money import format_gbp


def months_to_payoff(
    balance: float,
    annual_rate_pct: float,
    monthly_payment: float,
) -> int | None:
    if balance <= 0:
        return 0
    if monthly_payment <= 0:
        return None
    monthly_rate = annual_rate_pct / 100 / 12
    if monthly_rate <= 0:
        return int((balance / monthly_payment) + 0.999)
    if monthly_payment <= balance * monthly_rate:
        return None
    months = 0
    remaining = balance
    while remaining > 0.01 and months < 600:
        interest = remaining * monthly_rate
        principal = monthly_payment - interest
        if principal <= 0:
            return None
        remaining -= principal
        months += 1
    return months


def total_interest_paid(
    balance: float,
    annual_rate_pct: float,
    monthly_payment: float,
) -> float | None:
    months = months_to_payoff(balance, annual_rate_pct, monthly_payment)
    if months is None:
        return None
    if months == 0:
        return 0.0
    monthly_rate = annual_rate_pct / 100 / 12
    remaining = balance
    interest_total = 0.0
    for _ in range(months):
        interest = remaining * monthly_rate
        interest_total += interest
        principal = monthly_payment - interest
        remaining -= principal
        if remaining <= 0:
            break
    return round(interest_total, 2)


def add_months(start: date, months: int) -> date:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, 28)
    return date(year, month, day)


def _months_to_payoff(
    balance: float,
    annual_rate_pct: float,
    monthly_payment: float,
) -> int | None:
    return months_to_payoff(balance, annual_rate_pct, monthly_payment)


def _add_months(start: date, months: int) -> date:
    return add_months(start, months)


def priority_label(apr: float, monthly_interest: float, *, apr_known: bool = True) -> str:
    """APR-band priority. Monthly £ is not used — large low-APR balances were
    wrongly labelled Highest cost when interest ≥ £50/mo."""
    del monthly_interest
    if not apr_known or apr <= 0:
        return "APR unknown"
    if apr >= 20:
        return "Highest cost"
    if apr >= 12:
        return "High"
    if apr >= 6:
        return "Medium"
    return "Low"


def _scope_value(raw: object) -> str:
    return str(getattr(raw, "value", raw) or "")


def _debt_type_value(raw: object) -> str:
    return str(getattr(raw, "value", raw) or "")


def _apr_known(debt: FinanceLiability) -> bool:
    return bool(getattr(debt, "interest_rate_known", True)) and debt.interest_rate_pct > 0


def _repayable(liabilities: Iterable[FinanceLiability]) -> list[FinanceLiability]:
    return [item for item in liabilities if item.is_active and is_repayable_debt(item)]


def _filter_scope(
    liabilities: Iterable[FinanceLiability], scope: str | None
) -> list[FinanceLiability]:
    active = _repayable(liabilities)
    if scope in {None, "", "all"}:
        return active
    return [item for item in active if _scope_value(item.scope) == scope]


def _order_reason(debt: FinanceLiability, *, is_focus: bool) -> str:
    dtype = _debt_type_value(debt.debt_type)
    if dtype == "mortgage":
        return (
            "House mortgage (confirmed half-share of £164,421 joint) — "
            "long-term secured debt, not the same queue as a 36% card"
        )
    if not _apr_known(debt):
        return "APR unknown — order uses balance only until APR is recorded"
    if is_focus:
        return f"Highest known APR ({debt.interest_rate_pct:.1f}%) — avalanche focus"
    return f"Avalanche order by APR ({debt.interest_rate_pct:.1f}%)"


def analyse_debts(liabilities: list[FinanceLiability]) -> list[DebtAnalysisItem]:
    items: list[DebtAnalysisItem] = []
    for debt in _repayable(liabilities):
        if not debt.is_active:
            continue
        interest = (
            monthly_interest_gbp(debt.balance_gbp, debt.interest_rate_pct)
            if _apr_known(debt)
            else None
        )
        payment = debt.minimum_payment_gbp + debt.overpayment_gbp
        months = (
            months_to_payoff(debt.balance_gbp, debt.interest_rate_pct, payment)
            if _apr_known(debt)
            else None
        )
        apr_known = _apr_known(debt)
        score = (
            round(debt.interest_rate_pct * 10 + (interest or 0), 2)
            if apr_known
            else round(debt.balance_gbp / 1000.0, 2)
        )
        items.append(
            DebtAnalysisItem(
                id=debt.id,
                name=debt.name,
                scope=_scope_value(debt.scope),
                debt_type=_debt_type_value(debt.debt_type),
                balance_gbp=debt.balance_gbp,
                interest_rate_pct=debt.interest_rate_pct,
                minimum_payment_gbp=debt.minimum_payment_gbp,
                overpayment_gbp=debt.overpayment_gbp,
                monthly_interest_gbp=interest,
                months_to_payoff=months,
                priority_score=score,
                priority_label=priority_label(
                    debt.interest_rate_pct, interest or 0, apr_known=apr_known
                ),
                apr_known=apr_known,
            )
        )
    items.sort(key=lambda item: (-item.priority_score, -item.balance_gbp))
    return items


def _avalanche_order(active: list[FinanceLiability]) -> list[FinanceLiability]:
    """Highest known APR first; unknown-APR after; mortgage last among unknowns."""

    def sort_key(debt: FinanceLiability) -> tuple:
        dtype = _debt_type_value(debt.debt_type)
        is_mortgage = 1 if dtype == "mortgage" else 0
        if _apr_known(debt):
            return (0, -debt.interest_rate_pct, is_mortgage, -debt.balance_gbp)
        return (1, is_mortgage, -debt.balance_gbp, debt.name.lower())

    return sorted(active, key=sort_key)


def _focus_debt(ordered: list[FinanceLiability]) -> FinanceLiability | None:
    """Prefer highest-APR non-mortgage; fall back to first ordered row."""
    for debt in ordered:
        if _debt_type_value(debt.debt_type) != "mortgage" and _apr_known(debt):
            return debt
    for debt in ordered:
        if _debt_type_value(debt.debt_type) != "mortgage":
            return debt
    return ordered[0] if ordered else None


def _incomplete_reason(active: list[FinanceLiability]) -> str:
    unknown = [d.name for d in active if not _apr_known(d)]
    if not unknown:
        return ""
    if len(unknown) == 1:
        return f"APR unknown for {unknown[0]} — plan incomplete (no invented rate)."
    shown = ", ".join(unknown[:4])
    more = "…" if len(unknown) > 4 else ""
    return (
        f"APR unknown for {len(unknown)} debts ({shown}{more}) — "
        "plan incomplete (no invented rates)."
    )


def _milestones(ordered: list[FinanceLiability]) -> list[DebtPayoffMilestone]:
    """Simple cumulative payoff milestones when every debt in scope has APR."""
    if not ordered or any(not _apr_known(d) for d in ordered):
        return []
    remaining = [
        {
            "name": d.name,
            "balance": float(d.balance_gbp),
            "apr": float(d.interest_rate_pct),
            "payment": float(d.minimum_payment_gbp + d.overpayment_gbp),
            "type": _debt_type_value(d.debt_type),
        }
        for d in ordered
        if d.balance_gbp > 0
    ]
    if not remaining:
        return []
    milestones: list[DebtPayoffMilestone] = []
    month = 0
    while remaining and month < 120:
        month += 1
        focus = next(
            (row for row in remaining if row["type"] != "mortgage"),
            remaining[0],
        )
        # Pay minimums on all; extra focus capacity is ignored (mins only baseline).
        still: list[dict[str, Any]] = []
        for row in remaining:
            payment = row["payment"]
            if payment <= 0 and row["apr"] > 0:
                payment = monthly_interest_gbp(row["balance"], row["apr"])
            rate = row["apr"] / 100 / 12
            interest = row["balance"] * rate
            principal = max(payment - interest, 0.0)
            new_bal = row["balance"] - principal
            if new_bal > 0.01:
                still.append({**row, "balance": new_bal})
            elif row is focus or row["name"] == focus["name"]:
                milestones.append(
                    DebtPayoffMilestone(
                        month_index=month,
                        label=f"Month {month}",
                        focus_debt_name=row["name"],
                        remaining_total_gbp=round(
                            sum(item["balance"] for item in still), 2
                        ),
                        note=f"{row['name']} paid off (minimum payments only)",
                    )
                )
        remaining = still
        if len(milestones) >= 6:
            break
    if remaining:
        milestones.append(
            DebtPayoffMilestone(
                month_index=month,
                label=f"After month {month}",
                focus_debt_name=None,
                remaining_total_gbp=round(sum(item["balance"] for item in remaining), 2),
                note="Balances remain — raise payments or add extras to finish sooner",
            )
        )
    return milestones


def scenario_for_extra(
    liabilities: list[FinanceLiability],
    extra_gbp: float,
    *,
    scope: str | None = None,
) -> DebtScenarioResult:
    active = [item for item in _filter_scope(liabilities, scope) if item.balance_gbp > 0]
    if not active:
        return DebtScenarioResult(
            extra_gbp=extra_gbp,
            incomplete=True,
            reason="No active debts to model in this scope.",
        )
    ordered = _avalanche_order(active)
    target = _focus_debt(ordered)
    assert target is not None
    if not _apr_known(target):
        return DebtScenarioResult(
            extra_gbp=extra_gbp,
            incomplete=True,
            reason=f"APR is missing for {target.name} — cannot model extras.",
        )
    reason_suffix = (
        "highest APR"
        if _apr_known(target)
        else "largest balance (APR unknown)"
    )

    recorded_payment = target.minimum_payment_gbp + target.overpayment_gbp
    interest_only = monthly_interest_gbp(target.balance_gbp, target.interest_rate_pct)
    assumed_interest_only = False
    current_payment = recorded_payment
    if current_payment <= 0:
        if not _apr_known(target):
            return DebtScenarioResult(
                extra_gbp=extra_gbp,
                incomplete=True,
                reason=f"Minimum payment is £0.00 and APR is missing for {target.name}.",
            )
        if extra_gbp <= 0:
            return DebtScenarioResult(
                extra_gbp=extra_gbp,
                incomplete=True,
                reason=(
                    f"Minimum payment is £0.00 on {target.name}. "
                    f"Enter an extra amount to model payoff (interest-only baseline "
                    f"{format_gbp(interest_only)}/mo)."
                ),
            )
        current_payment = interest_only
        assumed_interest_only = True

    payment_with_extra = current_payment + extra_gbp
    months_current = months_to_payoff(
        target.balance_gbp, target.interest_rate_pct, current_payment
    )
    months_extra = months_to_payoff(
        target.balance_gbp, target.interest_rate_pct, payment_with_extra
    )
    interest_current = total_interest_paid(
        target.balance_gbp, target.interest_rate_pct, current_payment
    )
    interest_extra = total_interest_paid(
        target.balance_gbp, target.interest_rate_pct, payment_with_extra
    )
    if months_extra is None:
        return DebtScenarioResult(
            extra_gbp=extra_gbp,
            months_current=months_current,
            months_with_extra=months_extra,
            incomplete=True,
            reason=(
                f"Even with {format_gbp(extra_gbp)} extra, payment on {target.name} "
                f"does not cover interest."
            ),
        )
    if months_current is None and not assumed_interest_only:
        return DebtScenarioResult(
            extra_gbp=extra_gbp,
            months_current=months_current,
            months_with_extra=months_extra,
            incomplete=True,
            reason=f"Current payment on {target.name} does not cover interest.",
        )
    interest_saved = (
        round((interest_current or 0) - (interest_extra or 0), 2)
        if interest_extra is not None
        else None
    )
    if assumed_interest_only:
        reason = (
            f"Extra applied to {target.name} ({reason_suffix}). "
            f"Assumes interest-only ({format_gbp(interest_only)}/mo) because "
            f"minimum payment is £0.00."
        )
        months_saved = None if months_current is None else max(months_current - months_extra, 0)
    else:
        reason = f"Extra applied to {target.name} ({reason_suffix})."
        months_saved = (
            None if months_current is None else max(months_current - months_extra, 0)
        )
    return DebtScenarioResult(
        extra_gbp=extra_gbp,
        months_current=months_current,
        months_with_extra=months_extra,
        months_saved=months_saved,
        interest_current_gbp=interest_current,
        interest_with_extra_gbp=interest_extra,
        interest_saved_gbp=interest_saved,
        payoff_date=add_months(date.today(), months_extra).isoformat(),
        incomplete=False,
        reason=reason,
    )


def recommend_debt_strategy(
    liabilities: list[FinanceLiability],
    *,
    scope: str | None = None,
) -> DebtStrategyRecommendation:
    active = [item for item in _filter_scope(liabilities, scope) if item.balance_gbp > 0]
    analysis = analyse_debts(active if scope not in {None, "", "all"} else liabilities)
    if scope in {"personal", "business"}:
        analysis = [row for row in analysis if row.scope == scope]
    extras = [0, 100, 250, 500]
    scenarios = [
        scenario_for_extra(liabilities, extra, scope=scope) for extra in extras
    ]
    scope_label = {
        "personal": "Personal",
        "business": "Business",
    }.get(scope or "all", "All")

    if not active:
        return DebtStrategyRecommendation(
            strategy="none",
            scope=scope or "all",
            headline=f"{scope_label}: no active debts",
            message=(
                f"No repayable {scope_label.lower()} debts are recorded yet. "
                "Director's loan is not a debt to repay."
            ),
            incomplete=False,
            debts=[],
            payoff_order=[],
            analysis=analysis,
            scenarios=[],
        )

    ordered = _avalanche_order(active)
    target = _focus_debt(ordered)
    assert target is not None
    incomplete_reason = _incomplete_reason(active)
    incomplete = bool(incomplete_reason)

    payment = target.minimum_payment_gbp + target.overpayment_gbp
    interest_only = (
        monthly_interest_gbp(target.balance_gbp, target.interest_rate_pct)
        if _apr_known(target)
        else 0.0
    )
    assumed_interest_only = False
    if payment <= 0 and _apr_known(target):
        payment = interest_only
        assumed_interest_only = True
    months = (
        _months_to_payoff(target.balance_gbp, target.interest_rate_pct, payment)
        if _apr_known(target)
        else None
    )
    debt_free = (
        _add_months(date.today(), months).isoformat()
        if months is not None and not incomplete
        else None
    )

    debts: list[dict[str, Any]] = []
    payoff_order = analyse_debts(ordered)
    # Preserve avalanche order rather than re-sorting by score alone.
    by_id = {row.id: row for row in payoff_order}
    ordered_analysis: list[DebtAnalysisItem] = []
    for item in ordered:
        row = by_id.get(item.id)
        if row is None:
            continue
        ordered_analysis.append(row)
        item_payment = item.minimum_payment_gbp + item.overpayment_gbp
        if item_payment <= 0 and _apr_known(item):
            item_payment = monthly_interest_gbp(item.balance_gbp, item.interest_rate_pct)
        item_months = (
            _months_to_payoff(item.balance_gbp, item.interest_rate_pct, item_payment)
            if _apr_known(item)
            else None
        )
        debts.append(
            {
                "id": item.id,
                "name": item.name,
                "scope": _scope_value(item.scope),
                "debt_type": _debt_type_value(item.debt_type),
                "balance_gbp": item.balance_gbp,
                "interest_rate_pct": item.interest_rate_pct,
                "interest_rate_known": _apr_known(item),
                "minimum_payment_gbp": item.minimum_payment_gbp,
                "overpayment_gbp": item.overpayment_gbp,
                "months_to_payoff": item_months,
                "monthly_interest_gbp": (
                    monthly_interest_gbp(item.balance_gbp, item.interest_rate_pct)
                    if _apr_known(item)
                    else None
                ),
                "priority_label": row.priority_label,
                "order_reason": _order_reason(item, is_focus=item.id == target.id),
                "is_mortgage": _debt_type_value(item.debt_type) == "mortgage",
                "is_focus": item.id == target.id,
            }
        )

    strategy = "avalanche"
    strategy_label = "Avalanche (highest interest first)"
    if debt_free:
        date_clause = f"Estimated focus payoff: {debt_free}."
    elif incomplete:
        date_clause = incomplete_reason
    elif assumed_interest_only:
        date_clause = (
            f"Minimum payment is £0.00 — modelled as interest-only "
            f"({format_gbp(interest_only)}/mo), so balance does not fall without extras."
        )
    elif not _apr_known(target):
        date_clause = f"APR unknown for {target.name} — no debt-free date invented."
    else:
        date_clause = "Current payment is too low to cover interest."

    apr_bit = (
        f"{target.interest_rate_pct:.1f}%"
        if _apr_known(target)
        else "APR unknown"
    )
    return DebtStrategyRecommendation(
        strategy=strategy,
        scope=scope or "all",
        headline=f"{scope_label}: {strategy_label}",
        message=(
            f"Focus extra payments on {target.name} "
            f"({format_gbp(target.balance_gbp, decimals=0)} at {apr_bit}). "
            f"{date_clause}"
        ),
        incomplete=incomplete,
        incomplete_reason=incomplete_reason,
        focus_debt_id=target.id,
        focus_debt_name=target.name,
        debts=debts,
        payoff_order=ordered_analysis,
        milestones=_milestones(ordered),
        estimated_debt_free_date=debt_free,
        analysis=analysis,
        scenarios=scenarios,
    )


def recommend_dual_debt_strategies(
    liabilities: list[FinanceLiability],
) -> DualDebtStrategiesResponse:
    return DualDebtStrategiesResponse(
        personal=recommend_debt_strategy(liabilities, scope="personal"),
        business=recommend_debt_strategy(liabilities, scope="business"),
    )
