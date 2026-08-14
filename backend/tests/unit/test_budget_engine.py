"""Unit tests for the deterministic budget calculation engine."""

from decimal import Decimal

from app.services.finance.budget_engine import (
    BudgetDraftItem,
    BusinessSnapshotInput,
    DebtRecordInput,
    PersonalSnapshotInput,
    apply_overrides,
    calculate_budget_inputs,
    calculate_budget_totals,
    calculate_mandatory_commitments,
    generate_suggested_budget,
    merge_refresh_preserving_overrides,
    parse_budget_amount,
    recommended_strategy,
    to_monthly_amount,
)


def _item(**kwargs) -> BudgetDraftItem:
    defaults = dict(
        key="k",
        scope="personal",
        kind="essential",
        category="Bills",
        amount_gbp=100.0,
        source="snapshot",
        source_label="From active income record",
        is_generated=True,
        is_user_override=False,
        is_transfer=False,
        is_missing=False,
        notes="",
    )
    defaults.update(kwargs)
    return BudgetDraftItem(**defaults)


def test_frequency_conversion() -> None:
    assert to_monthly_amount(100, "monthly") == Decimal("100")
    assert to_monthly_amount(1200, "annual") == Decimal("100")
    weekly = to_monthly_amount(50, "weekly")
    fortnightly = to_monthly_amount(80, "fortnightly")
    expected_weekly = (Decimal("50") * Decimal("52") / Decimal("12")).quantize(
        Decimal("0.01")
    )
    expected_fortnightly = (Decimal("80") * Decimal("26") / Decimal("12")).quantize(
        Decimal("0.01")
    )
    assert weekly.quantize(Decimal("0.01")) == expected_weekly
    assert fortnightly.quantize(Decimal("0.01")) == expected_fortnightly
    assert weekly > Decimal("200")
    assert fortnightly > Decimal("170")


def test_parse_budget_amount_blank_is_missing() -> None:
    assert parse_budget_amount("") is None
    assert parse_budget_amount("   ") is None
    assert parse_budget_amount("0") == Decimal("0")
    assert parse_budget_amount("£1,234.56") == Decimal("1234.56")


def test_totals_income_expenditure_surplus() -> None:
    items = [
        _item(key="i", kind="income", category="Pay", amount_gbp=4000),
        _item(key="e", kind="essential", category="Bills", amount_gbp=1200),
        _item(key="d", kind="debt_minimum", category="Card min", amount_gbp=50),
        _item(key="o", kind="debt_overpayment", category="Extra", amount_gbp=150),
        _item(key="b", kind="buffer", category="Buffer", amount_gbp=200),
        _item(key="x", kind="discretionary", category="Spending", amount_gbp=400),
    ]
    totals = calculate_budget_totals(items, "personal")
    assert totals.income_gbp == 4000
    assert totals.essential_gbp == 1200
    assert totals.debt_minimum_gbp == 50
    assert totals.debt_overpayment_gbp == 150
    assert totals.buffer_gbp == 200
    assert totals.discretionary_gbp == 400
    assert totals.allocated_gbp == 2000
    assert totals.surplus_gbp == 2000
    assert totals.is_deficit is False


def test_totals_deficit_is_visible() -> None:
    items = [
        _item(key="i", kind="income", category="Pay", amount_gbp=500),
        _item(key="e", kind="essential", category="Bills", amount_gbp=800),
    ]
    totals = calculate_budget_totals(items)
    assert totals.surplus_gbp == -300
    assert totals.is_deficit is True


def test_missing_income_does_not_become_zero_surplus() -> None:
    items = [
        _item(key="i", kind="income", category="Pay", amount_gbp=None, is_missing=True),
        _item(key="e", kind="essential", category="Bills", amount_gbp=800),
    ]
    totals = calculate_budget_totals(items)
    assert totals.surplus_gbp is None
    assert totals.income_complete is False
    assert totals.has_missing_inputs is True
    assert "income" in totals.incomplete_reason.lower()


def test_missing_debt_payment_is_not_treated_as_zero() -> None:
    personal = PersonalSnapshotInput(exists=True, snapshot_id=1, monthly_income_gbp=3000)
    debts = [
        DebtRecordInput(
            id=9,
            scope="personal",
            name="MBNA",
            debt_type="credit_card",
            balance_gbp=2000,
            interest_rate_pct=22,
            minimum_payment_gbp=None,
        )
    ]
    inputs = calculate_budget_inputs(personal=personal, business=None, debts=debts)
    missing_debt = [m for m in inputs.missing if m.code == "debt_minimum"]
    assert missing_debt
    assert "MBNA" in missing_debt[0].message
    debt_item = next(i for i in inputs.items if i.kind == "debt_minimum")
    assert debt_item.is_missing is True
    assert debt_item.amount_gbp is None


def test_no_personal_snapshot_flags_missing_income() -> None:
    inputs = calculate_budget_inputs(
        personal=PersonalSnapshotInput(exists=False),
        business=None,
        debts=[],
    )
    assert any(m.code == "personal_income" for m in inputs.missing)
    assert recommended_strategy(inputs) == "stabilise"


def test_strategy_generation_uses_real_surplus_only() -> None:
    personal = PersonalSnapshotInput(
        exists=True,
        snapshot_id=1,
        monthly_income_gbp=4000,
        household_bills_gbp=1000,
    )
    debts = [
        DebtRecordInput(
            id=1,
            scope="personal",
            name="Card",
            debt_type="credit_card",
            balance_gbp=1500,
            interest_rate_pct=24.9,
            minimum_payment_gbp=40,
            overpayment_gbp=10,
        )
    ]
    inputs = calculate_budget_inputs(personal=personal, business=None, debts=debts)
    # Mandatory 1000 + 40 + recorded over 10 = 1050; unallocated = 2950
    stabilise = generate_suggested_budget(inputs, "stabilise")
    balanced = generate_suggested_budget(inputs, "balanced")
    attack = generate_suggested_budget(inputs, "debt_attack")

    assert stabilise.totals_consolidated.debt_minimum_gbp == 40
    assert balanced.totals_consolidated.debt_minimum_gbp == 40
    assert attack.totals_consolidated.debt_minimum_gbp == 40

    assert (
        attack.totals_consolidated.debt_overpayment_gbp
        > balanced.totals_consolidated.debt_overpayment_gbp
    )
    assert (
        balanced.totals_consolidated.debt_overpayment_gbp
        > stabilise.totals_consolidated.debt_overpayment_gbp
    )
    assert stabilise.totals_consolidated.buffer_gbp > attack.totals_consolidated.buffer_gbp

    # No invented income
    assert stabilise.totals_consolidated.income_gbp == 4000
    assert balanced.totals_consolidated.income_gbp == 4000
    assert attack.totals_consolidated.income_gbp == 4000


def test_no_surplus_does_not_invent_overpayment() -> None:
    personal = PersonalSnapshotInput(
        exists=True,
        snapshot_id=1,
        monthly_income_gbp=1000,
        household_bills_gbp=1000,
    )
    inputs = calculate_budget_inputs(personal=personal, business=None, debts=[])
    attack = generate_suggested_budget(inputs, "debt_attack")
    extras = [i for i in attack.items if i.source == "generated"]
    assert extras == []
    assert attack.totals_consolidated.surplus_gbp == 0


def test_override_retained_when_source_changes() -> None:
    generated = [
        _item(key="bills", kind="essential", category="Bills", amount_gbp=200, source="snapshot"),
    ]
    overridden = apply_overrides(generated, {"bills": 350})
    assert overridden[0].amount_gbp == 350
    assert overridden[0].is_user_override is True

    refreshed = [
        _item(key="bills", kind="essential", category="Bills", amount_gbp=220, source="snapshot"),
    ]
    merged = merge_refresh_preserving_overrides(overridden, refreshed)
    assert merged[0].amount_gbp == 350
    assert merged[0].is_user_override is True


def test_personal_business_separation_and_transfer() -> None:
    items = [
        _item(key="pi", scope="personal", kind="income", category="Salary", amount_gbp=3000),
        _item(key="bi", scope="business", kind="income", category="Turnover", amount_gbp=8000),
        _item(
            key="sal",
            scope="business",
            kind="essential",
            category="Salary paid",
            amount_gbp=3000,
            is_transfer=True,
        ),
        _item(key="be", scope="business", kind="essential", category="Costs", amount_gbp=2000),
    ]
    personal = calculate_budget_totals(items, "personal")
    business = calculate_budget_totals(items, "business")
    consolidated = calculate_budget_totals(items, "consolidated")

    assert personal.income_gbp == 3000
    assert business.income_gbp == 8000
    assert business.essential_gbp == 5000
    # Transfer excluded from consolidated expenditure
    assert consolidated.income_gbp == 11000
    assert consolidated.essential_gbp == 2000
    assert consolidated.surplus_gbp == 9000


def test_directors_loan_marked_as_transfer() -> None:
    personal = PersonalSnapshotInput(exists=True, snapshot_id=1, monthly_income_gbp=2000)
    debts = [
        DebtRecordInput(
            id=4,
            scope="business",
            name="DLA",
            debt_type="directors_loan",
            balance_gbp=5000,
            interest_rate_pct=0,
            minimum_payment_gbp=250,
        )
    ]
    inputs = calculate_budget_inputs(personal=personal, business=None, debts=debts)
    dla = next(i for i in inputs.items if "DLA" in i.category)
    assert dla.is_transfer is True
    consolidated = calculate_budget_totals(inputs.items, "consolidated")
    assert consolidated.debt_minimum_gbp == 0


def test_tax_reserve_is_not_guessed_as_monthly_provision() -> None:
    business = BusinessSnapshotInput(
        exists=True,
        snapshot_id=2,
        turnover_gbp=10000,
        expenses_gbp=4000,
        vat_reserve_gbp=800,
        corp_tax_reserve_gbp=500,
    )
    inputs = calculate_budget_inputs(
        personal=PersonalSnapshotInput(exists=False),
        business=business,
        debts=[],
    )
    tax_items = [i for i in inputs.items if i.kind == "tax_provision"]
    assert tax_items
    assert tax_items[0].is_missing is True
    assert tax_items[0].amount_gbp is None
    assert inputs.tax.vat_reserved_gbp == 800
    assert any("not a monthly provision" in note.lower() for note in inputs.tax.notes)


def test_mandatory_commitments() -> None:
    items = [
        _item(key="e", kind="essential", amount_gbp=100),
        _item(key="d", kind="debt_minimum", amount_gbp=40),
        _item(key="t", kind="tax_provision", amount_gbp=20),
        _item(key="o", kind="debt_overpayment", amount_gbp=99),
    ]
    assert calculate_mandatory_commitments(items) == Decimal("160")


def test_balanced_recommended_only_when_surplus_supports_it() -> None:
    healthy = calculate_budget_inputs(
        personal=PersonalSnapshotInput(
            exists=True, monthly_income_gbp=5000, household_bills_gbp=1000
        ),
        business=None,
        debts=[],
    )
    tight = calculate_budget_inputs(
        personal=PersonalSnapshotInput(
            exists=True, monthly_income_gbp=500, household_bills_gbp=800
        ),
        business=None,
        debts=[],
    )
    assert recommended_strategy(healthy) == "balanced"
    assert recommended_strategy(tight) == "stabilise"
