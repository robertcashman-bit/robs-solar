"""Debt payoff strategy, priority scoring, and overpayment scenarios."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.schemas.finance import (
    DebtAnalysisItem,
    DebtScenarioResult,
    DebtStrategyRecommendation,
    FinanceLiability,
)
from app.services.finance.finance_calc import is_repayable_debt, monthly_interest_gbp


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


def priority_label(apr: float, monthly_interest: float) -> str:
    if apr >= 20 or monthly_interest >= 50:
        return "Highest cost"
    if apr >= 12 or monthly_interest >= 20:
        return "High"
    if apr >= 6:
        return "Medium"
    return "Low"


def _repayable(liabilities: list[FinanceLiability]) -> list[FinanceLiability]:
    return [item for item in liabilities if item.is_active and is_repayable_debt(item)]


def analyse_debts(liabilities: list[FinanceLiability]) -> list[DebtAnalysisItem]:
    items: list[DebtAnalysisItem] = []
    for debt in _repayable(liabilities):
        if not debt.is_active:
            continue
        interest = monthly_interest_gbp(debt.balance_gbp, debt.interest_rate_pct)
        payment = debt.minimum_payment_gbp + debt.overpayment_gbp
        months = months_to_payoff(debt.balance_gbp, debt.interest_rate_pct, payment)
        score = round(debt.interest_rate_pct * 10 + interest, 2)
        items.append(
            DebtAnalysisItem(
                id=debt.id,
                name=debt.name,
                scope=debt.scope.value if hasattr(debt.scope, "value") else str(debt.scope),
                debt_type=(
                    debt.debt_type.value
                    if hasattr(debt.debt_type, "value")
                    else str(debt.debt_type)
                ),
                balance_gbp=debt.balance_gbp,
                interest_rate_pct=debt.interest_rate_pct,
                minimum_payment_gbp=debt.minimum_payment_gbp,
                overpayment_gbp=debt.overpayment_gbp,
                monthly_interest_gbp=interest,
                months_to_payoff=months,
                priority_score=score,
                priority_label=priority_label(debt.interest_rate_pct, interest),
                apr_known=debt.interest_rate_pct >= 0,
            )
        )
    items.sort(key=lambda item: (-item.priority_score, -item.balance_gbp))
    return items


def scenario_for_extra(
    liabilities: list[FinanceLiability],
    extra_gbp: float,
) -> DebtScenarioResult:
    active = [
        item
        for item in _repayable(liabilities)
        if item.balance_gbp > 0
    ]
    if not active:
        return DebtScenarioResult(
            extra_gbp=extra_gbp,
            incomplete=True,
            reason="No active debts to model.",
        )
    known_apr = [
        item
        for item in active
        if item.interest_rate_known and item.interest_rate_pct > 0
    ]
    if known_apr:
        target = max(known_apr, key=lambda item: item.interest_rate_pct)
        reason_suffix = "highest APR"
    else:
        target = max(active, key=lambda item: item.balance_gbp)
        reason_suffix = "largest balance (APR unknown)"
    current_payment = target.minimum_payment_gbp + target.overpayment_gbp
    if current_payment <= 0 or (target.interest_rate_known and target.interest_rate_pct < 0):
        return DebtScenarioResult(
            extra_gbp=extra_gbp,
            incomplete=True,
            reason=f"Payment or APR is missing for {target.name}.",
        )
    months_current = months_to_payoff(target.balance_gbp, target.interest_rate_pct, current_payment)
    months_extra = months_to_payoff(
        target.balance_gbp, target.interest_rate_pct, current_payment + extra_gbp
    )
    interest_current = total_interest_paid(
        target.balance_gbp, target.interest_rate_pct, current_payment
    )
    interest_extra = total_interest_paid(
        target.balance_gbp, target.interest_rate_pct, current_payment + extra_gbp
    )
    if months_current is None or months_extra is None:
        return DebtScenarioResult(
            extra_gbp=extra_gbp,
            months_current=months_current,
            months_with_extra=months_extra,
            incomplete=True,
            reason=f"Current payment on {target.name} does not cover interest.",
        )
    interest_saved = (
        round(interest_current - interest_extra, 2)
        if interest_current is not None and interest_extra is not None
        else None
    )
    return DebtScenarioResult(
        extra_gbp=extra_gbp,
        months_current=months_current,
        months_with_extra=months_extra,
        months_saved=max(months_current - months_extra, 0),
        interest_current_gbp=interest_current,
        interest_with_extra_gbp=interest_extra,
        interest_saved_gbp=interest_saved,
        payoff_date=add_months(date.today(), months_extra).isoformat(),
        incomplete=False,
        reason=f"Extra applied to {target.name} ({reason_suffix}).",
    )


def recommend_debt_strategy(liabilities: list[FinanceLiability]) -> DebtStrategyRecommendation:
    active = [item for item in _repayable(liabilities) if item.balance_gbp > 0]
    analysis = analyse_debts(liabilities)
    extras = [0, 100, 250, 500]
    scenarios = [scenario_for_extra(liabilities, extra) for extra in extras]
    if not active:
        return DebtStrategyRecommendation(
            strategy="none",
            headline="No active debts",
            message=(
                "No credit cards, loans, or mortgages are recorded yet. "
                "Log in to your bank to pull them in, or add one below."
            ),
            debts=[],
            analysis=analysis,
            scenarios=[],
        )

    snowball = sorted(active, key=lambda debt: debt.balance_gbp)
    avalanche = sorted(active, key=lambda debt: debt.interest_rate_pct, reverse=True)
    chosen = avalanche
    strategy = "avalanche"

    if snowball and avalanche and snowball[0].id != avalanche[0].id:
        sb_months = _months_to_payoff(
            snowball[0].balance_gbp,
            snowball[0].interest_rate_pct,
            snowball[0].minimum_payment_gbp + snowball[0].overpayment_gbp,
        )
        av_months = _months_to_payoff(
            avalanche[0].balance_gbp,
            avalanche[0].interest_rate_pct,
            avalanche[0].minimum_payment_gbp + avalanche[0].overpayment_gbp,
        )
        if sb_months is not None and av_months is not None and sb_months < av_months:
            chosen = snowball
            strategy = "snowball"

    target = chosen[0]
    payment = target.minimum_payment_gbp + target.overpayment_gbp
    months = _months_to_payoff(target.balance_gbp, target.interest_rate_pct, payment)
    debt_free = _add_months(date.today(), months).isoformat() if months is not None else None

    debts: list[dict[str, Any]] = []
    for item in active:
        item_months = _months_to_payoff(
            item.balance_gbp,
            item.interest_rate_pct,
            item.minimum_payment_gbp + item.overpayment_gbp,
        )
        debts.append(
            {
                "id": item.id,
                "name": item.name,
                "balance_gbp": item.balance_gbp,
                "interest_rate_pct": item.interest_rate_pct,
                "minimum_payment_gbp": item.minimum_payment_gbp,
                "overpayment_gbp": item.overpayment_gbp,
                "months_to_payoff": item_months,
                "monthly_interest_gbp": monthly_interest_gbp(
                    item.balance_gbp, item.interest_rate_pct
                ),
                "priority_label": next(
                    (row.priority_label for row in analysis if row.id == item.id),
                    "Medium",
                ),
            }
        )

    if strategy == "avalanche":
        strategy_label = "Avalanche (highest interest first)"
    else:
        strategy_label = "Snowball (smallest balance first)"
    return DebtStrategyRecommendation(
        strategy=strategy,
        headline=f"Recommended: {strategy_label}",
        message=(
            f"Focus extra payments on {target.name} ({target.balance_gbp:.0f} GBP at "
            f"{target.interest_rate_pct:.1f}%). "
            f"Estimated debt-free date for this debt: "
            f"{debt_free or 'payment too low to cover interest'}."
        ),
        debts=debts,
        estimated_debt_free_date=debt_free,
        analysis=analysis,
        scenarios=scenarios,
    )
