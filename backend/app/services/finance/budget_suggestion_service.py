"""Suggested budget engine.

Builds Stabilise, Balanced, and Debt Attack plans from recorded finances.
Does not invent income or treat unused credit as spendable money.

Priority order used when allocating surplus:
1. essential living / operating costs
2. contractual minimum debt payments
3. tax reserves
4. prevent unauthorised overdraft
5. reasonable cash buffer
6. high-interest debt reduction
7. discretionary spending
8. lower-priority accelerated repayment
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.finance.finance_calc import (
    AccountView,
    LiabilityView,
    SnapshotView,
    compute_totals,
    is_repayable_debt,
    monthly_interest_gbp,
)

PERSONAL_CATEGORIES = [
    "Household / mortgage contribution",
    "Utilities",
    "Food",
    "Transport",
    "Insurance",
    "Phone / communications",
    "Family support",
    "Debt minimum payments",
    "Debt overpayments",
    "Personal spending",
    "Subscriptions",
    "Emergency buffer",
    "Savings",
    "Other",
]

BUSINESS_CATEGORIES = [
    "Salary",
    "Vehicle finance",
    "Loan repayments",
    "Software / IT",
    "Telephone",
    "Insurance",
    "Professional costs",
    "Travel",
    "Accountancy",
    "Tax reserve",
    "VAT reserve",
    "Corporation tax reserve",
    "Debt overpayment",
    "Business buffer",
    "Other operating expenses",
]

STYLE_META = {
    "stabilise": {
        "name": "Stabilise",
        "explanation": (
            "Protects cashflow and tax reserves first, with conservative debt "
            "overpayments so you are less likely to run short."
        ),
        "debt_intensity": "low",
        "buffer_fraction": 0.15,
        "buffer_cap": 2000.0,
        "min_buffer": 500.0,
        "overpay_fraction": 0.15,
        "discretionary_keep": 0.85,
    },
    "balanced": {
        "name": "Balanced",
        "explanation": (
            "Maintains a reasonable cash reserve while directing additional "
            "money toward expensive debt."
        ),
        "debt_intensity": "medium",
        "buffer_fraction": 0.10,
        "buffer_cap": 1200.0,
        "min_buffer": 300.0,
        "overpay_fraction": 0.40,
        "discretionary_keep": 0.70,
    },
    "debt_attack": {
        "name": "Debt Attack",
        "explanation": (
            "Puts leftover cash toward the highest-interest revolving credit, "
            "keeping only a minimum emergency and business buffer."
        ),
        "debt_intensity": "high",
        "buffer_fraction": 0.04,
        "buffer_cap": 400.0,
        "min_buffer": 200.0,
        "overpay_fraction": 0.75,
        "discretionary_keep": 0.40,
    },
}


@dataclass
class BudgetGap:
    field: str
    message: str
    href: str = "/finance/personal"


@dataclass
class BudgetLineDraft:
    scope: str
    category: str
    amount_gbp: float
    source: str
    source_note: str
    is_custom: bool = False
    sort_order: int = 0


@dataclass
class SuggestedBudget:
    style: str
    name: str
    explanation: str
    debt_intensity: str
    cash_buffer_target_gbp: float
    discretionary_gbp: float
    tax_reserve_gbp: float
    income_gbp: float
    committed_gbp: float
    debt_payment_gbp: float
    debt_overpayment_gbp: float
    surplus_gbp: float
    shortfall_gbp: float
    recommended: bool
    incomplete: bool
    gaps: list[BudgetGap]
    lines: list[BudgetLineDraft]
    notes: str = ""


@dataclass
class SuggestionBundle:
    income_gbp: float
    personal_income_known: bool
    default_style: str
    options: list[SuggestedBudget] = field(default_factory=list)
    gaps: list[BudgetGap] = field(default_factory=list)


def _round(value: float) -> float:
    return round(max(value, 0.0), 2)


def _money(value: float) -> float:
    return round(value, 2)


def _gaps(
    personal: SnapshotView | None,
    debts: list[LiabilityView],
) -> list[BudgetGap]:
    gaps: list[BudgetGap] = []
    if personal is None or personal.monthly_income_gbp <= 0:
        gaps.append(
            BudgetGap(
                field="monthly_income_gbp",
                message="No regular personal income recorded",
                href="/finance/personal",
            )
        )
    if personal is None or personal.household_bills_gbp <= 0:
        gaps.append(
            BudgetGap(
                field="household_bills_gbp",
                message="No regular household bills recorded",
                href="/finance/personal",
            )
        )
    for debt in debts:
        if not is_repayable_debt(debt):
            continue
        if debt.balance_gbp > 0 and debt.minimum_payment_gbp <= 0:
            gaps.append(
                BudgetGap(
                    field=f"minimum_payment:{debt.name}",
                    message=f"Monthly payment missing for {debt.name}",
                    href="/finance/debts",
                )
            )
        if debt.balance_gbp > 0 and debt.interest_rate_pct < 0:
            gaps.append(
                BudgetGap(
                    field=f"apr:{debt.name}",
                    message=f"APR missing for {debt.name}",
                    href="/finance/debts",
                )
            )
    return gaps


def _personal_discretionary(personal: SnapshotView | None, household: float) -> float:
    if personal is None:
        return 0.0
    spending = personal.monthly_spending_gbp
    if spending <= 0:
        return 0.0
    return _round(max(spending - household, 0.0))


def _tax_topups(
    business: SnapshotView | None, vat_held: float, corp_held: float
) -> tuple[float, float]:
    if business is None:
        return 0.0, 0.0
    vat_need = business.expenses_gbp * 0.20 if business.expenses_gbp > 0 else 0.0
    profit = business.profit_estimate_gbp or (business.turnover_gbp - business.expenses_gbp)
    corp_need = max(profit, 0.0) * 0.19 / 12.0
    vat_topup = _round(max(vat_need - vat_held, 0.0) / 3.0) if vat_need else 0.0
    corp_topup = _round(max(corp_need - (corp_held / 12.0), 0.0))
    return vat_topup, corp_topup


def _allocate(
    leftover: float, current_value: float, keep_fraction: float, spend_fraction: float
) -> tuple[float, float]:
    if leftover <= 0:
        return 0.0, 0.0
    desired = (
        _round(current_value * keep_fraction)
        if current_value
        else _round(leftover * (1.0 - spend_fraction))
    )
    kept = _round(min(desired, leftover))
    return kept, _round(max(leftover - kept, 0.0))


def _build_style(
    style: str,
    *,
    personal_income: float,
    business_income: float,
    household: float,
    personal_mins: float,
    business_mins: float,
    operating: float,
    vat_topup: float,
    corp_topup: float,
    current_discretionary: float,
    overdraft: float,
    gaps: list[BudgetGap],
    highest_apr_name: str | None,
) -> SuggestedBudget:
    meta = STYLE_META[style]
    tax = _round(vat_topup + corp_topup)
    income = _round(personal_income + business_income)
    overdraft_reserve = min(overdraft, 250.0) if overdraft else 0.0
    personal_essentials = _round(household + personal_mins + overdraft_reserve)
    business_essentials = _round(operating + business_mins + tax)
    personal_leftover = personal_income - personal_essentials
    business_leftover = business_income - business_essentials

    personal_buffer_target = 0.0
    if personal_income > 0:
        personal_buffer_target = min(personal_income * meta["buffer_fraction"], meta["buffer_cap"])
        if personal_leftover > 0:
            personal_buffer_target = max(personal_buffer_target, meta["min_buffer"])
    business_buffer_target = (
        min(max(business_income * 0.03, 0.0), 800.0) if business_income else 0.0
    )
    if style == "debt_attack":
        business_buffer_target = min(business_buffer_target, 250.0)

    if personal_leftover < 0:
        personal_buffer = 0.0
        discretionary = 0.0
        personal_overpay = 0.0
        personal_surplus = personal_leftover
    else:
        personal_buffer = _round(min(personal_buffer_target, personal_leftover))
        after_buffer = personal_leftover - personal_buffer
        discretionary, personal_overpay = _allocate(
            after_buffer,
            current_discretionary,
            meta["discretionary_keep"],
            meta["overpay_fraction"],
        )
        if style == "debt_attack" and after_buffer > 0:
            personal_overpay = _round(after_buffer * meta["overpay_fraction"])
            discretionary = _round(max(after_buffer - personal_overpay, 0.0))
        personal_surplus = _round(
            personal_income
            - personal_essentials
            - personal_buffer
            - discretionary
            - personal_overpay
        )

    if business_leftover < 0:
        business_buffer = 0.0
        business_overpay = 0.0
        business_surplus = business_leftover
    else:
        business_buffer = _round(min(business_buffer_target, business_leftover))
        leftover_after_buffer = max(business_leftover - business_buffer, 0.0)
        overpay_share = 0.1 if style == "stabilise" else 0.25 if style == "balanced" else 0.5
        business_overpay = _round(leftover_after_buffer * overpay_share)
        business_surplus = _round(
            business_income - business_essentials - business_buffer - business_overpay
        )

    buffer = _round(personal_buffer + business_buffer)
    overpay = _round(personal_overpay + business_overpay)
    surplus = _money(personal_surplus + business_surplus)

    shortfall = _round(abs(min(surplus, 0.0)))
    committed = _round(household + personal_mins + business_mins + operating + tax)
    lines: list[BudgetLineDraft] = []

    def add(
        scope: str,
        category: str,
        amount: float,
        source: str,
        note: str,
        order: int,
        custom: bool = False,
    ) -> None:
        keep_zero = {
            "Debt overpayments",
            "Debt overpayment",
            "Emergency buffer",
            "Business buffer",
        }
        if amount <= 0 and category not in keep_zero:
            return
        lines.append(
            BudgetLineDraft(
                scope=scope,
                category=category,
                amount_gbp=_round(amount),
                source=source,
                source_note=note,
                is_custom=custom,
                sort_order=order,
            )
        )

    add(
        "personal",
        "Household / mortgage contribution",
        household,
        "snapshot" if household else "suggested",
        (
            "Based on household bills in the latest personal snapshot"
            if household
            else "No household amount recorded"
        ),
        10,
    )
    add(
        "personal",
        "Debt minimum payments",
        personal_mins,
        "debt_minimum",
        "Based on current minimum debt payments",
        20,
    )
    add(
        "personal",
        "Debt overpayments",
        personal_overpay,
        "suggested",
        (
            f"Suggested extra toward {highest_apr_name}"
            if highest_apr_name
            else "Suggested extra toward highest-cost debt"
        ),
        30,
    )
    add(
        "personal",
        "Personal spending",
        discretionary,
        "snapshot" if current_discretionary else "suggested",
        (
            "Based on snapshot spending after household bills"
            if current_discretionary
            else "Suggested discretionary allowance"
        ),
        40,
    )
    add(
        "personal",
        "Emergency buffer",
        personal_buffer,
        "suggested",
        "Suggested personal cash buffer contribution",
        50,
    )
    add(
        "business",
        "Other operating expenses",
        operating,
        "snapshot" if operating else "suggested",
        (
            "Based on latest business expense snapshot"
            if operating
            else "No business expenses recorded"
        ),
        60,
    )
    add(
        "business",
        "Loan repayments",
        business_mins,
        "debt_minimum",
        "Based on current business debt minimums",
        70,
    )
    add(
        "business",
        "VAT reserve",
        vat_topup,
        "suggested",
        "Based on ~20% of recorded expenses, spread over a quarter",
        80,
    )
    add(
        "business",
        "Corporation tax reserve",
        corp_topup,
        "suggested",
        "Based on 19% of estimated monthly profit",
        90,
    )
    add(
        "business",
        "Debt overpayment",
        business_overpay,
        "suggested",
        "Suggested extra toward the highest-cost business liability",
        100,
    )
    add(
        "business",
        "Business buffer",
        business_buffer,
        "suggested",
        "Suggested operating cash buffer",
        110,
    )

    notes = ""
    if shortfall > 0:
        notes = f"Projected shortfall of £{shortfall:,.0f} this month with the recorded income."
    elif not income:
        notes = "Income is missing, so this is a spending plan only — surplus cannot be calculated."

    return SuggestedBudget(
        style=style,
        name=meta["name"],
        explanation=meta["explanation"],
        debt_intensity=meta["debt_intensity"],
        cash_buffer_target_gbp=_round(buffer),
        discretionary_gbp=_round(discretionary),
        tax_reserve_gbp=tax,
        income_gbp=_round(income),
        committed_gbp=committed,
        debt_payment_gbp=_round(personal_mins + business_mins + overpay),
        debt_overpayment_gbp=_round(overpay),
        surplus_gbp=round(surplus, 2),
        shortfall_gbp=shortfall,
        recommended=False,
        incomplete=bool(gaps) or income <= 0,
        gaps=list(gaps),
        lines=lines,
        notes=notes,
    )


def suggest_budgets(
    accounts: list[AccountView],
    liabilities: list[LiabilityView],
    personal: SnapshotView | None,
    business: SnapshotView | None,
) -> SuggestionBundle:
    totals = compute_totals(accounts, liabilities, personal, business)
    debts = [item for item in liabilities if item.is_active and item.balance_gbp > 0]
    repayable = [item for item in debts if is_repayable_debt(item)]
    gaps = _gaps(personal, repayable)

    income = personal.monthly_income_gbp if personal else 0.0
    business_income = business.turnover_gbp if business else 0.0
    household = personal.household_bills_gbp if personal else 0.0
    personal_mins = sum(
        debt.minimum_payment_gbp for debt in repayable if debt.scope == "personal"
    )
    mortgage_mins = sum(
        debt.minimum_payment_gbp for debt in debts if debt.debt_type == "mortgage"
    )
    if household > 0 and mortgage_mins > 0:
        gaps.append(
            BudgetGap(
                field="mortgage_overlap",
                message=(
                    "Household bills and a mortgage payment are both recorded. "
                    "If the mortgage is already inside household bills, reduce "
                    "that category so it is not counted twice."
                ),
                href="/finance/personal",
            )
        )
    business_mins = sum(
        debt.minimum_payment_gbp for debt in repayable if debt.scope == "business"
    )
    operating = business.expenses_gbp if business else 0.0
    vat_topup, corp_topup = _tax_topups(
        business, totals.vat_reserve_gbp, totals.corp_tax_reserve_gbp
    )
    discretionary = _personal_discretionary(personal, household)
    overdraft = totals.personal_overdraft_gbp + totals.business_overdraft_gbp
    highest = max(repayable, key=lambda d: d.interest_rate_pct, default=None)

    options = [
        _build_style(
            style,
            personal_income=income,
            business_income=business_income,
            household=household,
            personal_mins=personal_mins,
            business_mins=business_mins,
            operating=operating,
            vat_topup=vat_topup,
            corp_topup=corp_topup,
            current_discretionary=discretionary,
            overdraft=overdraft,
            gaps=gaps,
            highest_apr_name=highest.name if highest else None,
        )
        for style in ("stabilise", "balanced", "debt_attack")
    ]

    default_style = "balanced"
    non_negative = [item for item in options if item.surplus_gbp >= 0 and income > 0]
    if non_negative:
        preferred = next(
            (item for item in non_negative if item.style == "balanced"),
            non_negative[0],
        )
        default_style = preferred.style
    for item in options:
        item.recommended = item.style == default_style

    return SuggestionBundle(
        income_gbp=_round(income + business_income),
        personal_income_known=income > 0,
        default_style=default_style,
        options=options,
        gaps=gaps,
    )


def summarise_lines(
    lines: list[BudgetLineDraft] | list[object], income_gbp: float
) -> dict[str, float]:
    """Recalculate plan totals from editable lines."""
    total = 0.0
    debt_pay = 0.0
    overpay = 0.0
    buffer = 0.0
    discretionary = 0.0
    tax = 0.0
    for line in lines:
        amount = float(getattr(line, "amount_gbp"))
        category = str(getattr(line, "category"))
        total += amount
        if category in {"Debt minimum payments", "Loan repayments"}:
            debt_pay += amount
        elif category in {"Debt overpayments", "Debt overpayment"}:
            overpay += amount
            debt_pay += amount
        elif category in {"Emergency buffer", "Business buffer", "Savings"}:
            buffer += amount
        elif category in {"Personal spending", "Subscriptions", "Other"}:
            discretionary += amount
        elif category in {"Tax reserve", "VAT reserve", "Corporation tax reserve"}:
            tax += amount
    surplus = round(income_gbp - total, 2)
    return {
        "income_gbp": round(income_gbp, 2),
        "committed_gbp": round(total - discretionary - overpay - buffer, 2),
        "total_spending_gbp": round(total, 2),
        "debt_payment_gbp": round(debt_pay, 2),
        "debt_overpayment_gbp": round(overpay, 2),
        "buffer_gbp": round(buffer, 2),
        "discretionary_gbp": round(discretionary, 2),
        "tax_reserve_gbp": round(tax, 2),
        "surplus_gbp": surplus,
        "shortfall_gbp": round(abs(min(surplus, 0.0)), 2),
    }


def highest_cost_target(liabilities: list[LiabilityView]) -> str | None:
    active = [
        item
        for item in liabilities
        if item.is_active and item.balance_gbp > 0 and is_repayable_debt(item)
    ]
    if not active:
        return None
    target = max(
        active,
        key=lambda item: (
            item.interest_rate_pct,
            monthly_interest_gbp(item.balance_gbp, item.interest_rate_pct),
        ),
    )
    return target.name
