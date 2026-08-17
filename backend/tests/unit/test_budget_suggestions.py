"""Unit tests for suggested budget engine."""

from app.services.finance.budget_suggestion_service import (
    BudgetLineDraft,
    suggest_budgets,
    summarise_lines,
)
from app.services.finance.finance_calc import AccountView, LiabilityView, SnapshotView


def _bundle():
    return suggest_budgets(
        [AccountView(1, "personal", "current", "Current", 1800)],
        [
            LiabilityView(1, "personal", "MBNA", "credit_card", 2400, 24.9, 40),
            LiabilityView(2, "personal", "Loan", "loan", 3000, 6.9, 120),
        ],
        SnapshotView(
            monthly_income_gbp=4200,
            monthly_spending_gbp=2100,
            household_bills_gbp=900,
            debt_repayments_gbp=160,
        ),
        SnapshotView(
            turnover_gbp=8000,
            expenses_gbp=2500,
            vat_reserve_gbp=400,
            corp_tax_reserve_gbp=200,
            profit_estimate_gbp=5500,
        ),
    )


def test_three_named_styles_are_returned() -> None:
    bundle = _bundle()
    assert [item.style for item in bundle.options] == ["stabilise", "balanced", "debt_attack"]
    assert bundle.personal_income_known is True
    assert bundle.default_style in {"stabilise", "balanced", "debt_attack"}


def test_balanced_is_default_when_surplus_exists() -> None:
    bundle = _bundle()
    assert bundle.default_style == "balanced"
    recommended = next(item for item in bundle.options if item.recommended)
    assert recommended.style == "balanced"


def test_debt_attack_overpays_more_than_stabilise() -> None:
    bundle = _bundle()
    by_style = {item.style: item for item in bundle.options}
    assert by_style["debt_attack"].debt_overpayment_gbp > by_style["stabilise"].debt_overpayment_gbp
    assert by_style["debt_attack"].discretionary_gbp <= by_style["balanced"].discretionary_gbp


def test_suggested_lines_are_editable_drafts() -> None:
    bundle = _bundle()
    for option in bundle.options:
        assert option.lines
        assert all(line.amount_gbp >= 0 for line in option.lines)


def test_missing_income_is_marked_incomplete() -> None:
    bundle = suggest_budgets([], [], None, None)
    assert bundle.personal_income_known is False
    assert any("income" in gap.message.lower() for gap in bundle.gaps)
    assert all(option.incomplete for option in bundle.options)


def test_does_not_invent_income_to_force_balance() -> None:
    bundle = suggest_budgets(
        [],
        [LiabilityView(1, "personal", "Card", "credit_card", 5000, 29.9, 150)],
        SnapshotView(monthly_income_gbp=200, monthly_spending_gbp=800, household_bills_gbp=400),
        None,
    )
    for option in bundle.options:
        assert option.income_gbp == 200
        assert option.shortfall_gbp > 0


def test_directors_loan_is_not_a_budget_minimum() -> None:
    bundle = suggest_budgets(
        [],
        [LiabilityView(1, "business", "DLA", "directors_loan", 20000, 0, 500)],
        SnapshotView(monthly_income_gbp=4000, household_bills_gbp=200),
        None,
    )
    mins = [
        line.amount_gbp
        for line in bundle.options[0].lines
        if line.category in {"Debt minimum payments", "Loan repayments"}
    ]
    assert mins == [] or all(amount == 0 for amount in mins)


def test_bundle_income_includes_business_turnover() -> None:
    bundle = _bundle()
    assert bundle.income_gbp == 12200
    assert all(option.income_gbp == 12200 for option in bundle.options)


def test_mortgage_minimum_stays_in_debt_lines() -> None:
    bundle = suggest_budgets(
        [],
        [LiabilityView(1, "personal", "Home", "mortgage", 180000, 4.5, 850)],
        SnapshotView(monthly_income_gbp=4000, household_bills_gbp=200),
        None,
    )
    mins = next(
        line
        for line in bundle.options[0].lines
        if line.category == "Debt minimum payments"
    )
    household = next(
        line
        for line in bundle.options[0].lines
        if line.category == "Household / mortgage contribution"
    )
    assert mins.amount_gbp == 850
    assert household.amount_gbp == 200
    assert any("mortgage" in gap.message.lower() for gap in bundle.gaps)


def test_summarise_lines_recalculates_surplus() -> None:
    totals = summarise_lines(
        [
            BudgetLineDraft("personal", "Household / mortgage contribution", 900, "snapshot", ""),
            BudgetLineDraft("personal", "Debt overpayments", 200, "user", ""),
            BudgetLineDraft("personal", "Personal spending", 400, "user", ""),
        ],
        2000,
    )
    assert totals["surplus_gbp"] == 500
    assert totals["debt_overpayment_gbp"] == 200
    assert totals["discretionary_gbp"] == 400
