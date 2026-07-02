"""Debt payoff strategy calculations."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.schemas.finance import DebtStrategyRecommendation, FinanceLiability


def _months_to_payoff(
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
    # Check payment covers interest
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


def _add_months(start: date, months: int) -> date:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, 28)
    return date(year, month, day)


def recommend_debt_strategy(liabilities: list[FinanceLiability]) -> DebtStrategyRecommendation:
    active = [item for item in liabilities if item.is_active and item.balance_gbp > 0]
    if not active:
        return DebtStrategyRecommendation(
            strategy="none",
            headline="No active debts",
            message=(
                "You have no recorded debts. Add liabilities on the Debts page "
                "to get payoff recommendations."
            ),
            debts=[],
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
    )
