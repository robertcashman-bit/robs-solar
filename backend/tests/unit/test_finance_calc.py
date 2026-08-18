"""Unit tests for canonical finance calculations."""

from types import SimpleNamespace

from app.services.finance.finance_calc import (
    AccountView,
    LiabilityView,
    MonthlyFlow,
    SnapshotView,
    company_position,
    compute_totals,
    directors_loan_sides,
    external_debt_gbp,
    liabilities_from_schema,
    monthly_interest_from_debts,
    monthly_interest_gbp,
    personal_net_worth,
    pick_open_banking_flow,
    previous_month_key,
    resolve_monthly_flow,
)


def test_monthly_interest_uses_apr_over_twelve() -> None:
    assert monthly_interest_gbp(1200, 12) == 12.0
    assert monthly_interest_gbp(0, 24) == 0.0
    assert monthly_interest_gbp(500, 0) == 0.0


def test_assets_sum_active_values_only() -> None:
    totals = compute_totals(
        [
            AccountView(1, "personal", "current", "Current", 2000),
            AccountView(2, "personal", "pension", "Pension", 40000),
            AccountView(3, "personal", "property", "Home equity", 80000),
            AccountView(4, "personal", "pension", "Old pension", 1000, is_active=False),
        ],
        [],
    )
    assert totals.total_assets_gbp == 122000
    assert totals.pension_gbp == 40000
    assert totals.property_gbp == 80000


def test_personal_and_business_debt_stay_separate() -> None:
    totals = compute_totals(
        [],
        [
            LiabilityView(1, "personal", "MBNA", "credit_card", 800, 22.9, 25),
            LiabilityView(2, "business", "Van finance", "business_loan", 4000, 8.0, 180),
            LiabilityView(3, "personal", "Lloyds loan", "loan", 10923.14, 6.0, 200),
            LiabilityView(4, "personal", "House", "mortgage", 82210.50, 4.0, 900),
        ],
    )
    assert totals.personal_debt_gbp == 800 + 10923.14 + 82210.50
    assert totals.business_debt_gbp == 4000
    assert totals.credit_card_gbp == 800
    assert totals.personal_credit_card_gbp == 800
    assert totals.loan_gbp == 4000
    assert totals.personal_loan_gbp == 10923.14
    assert totals.mortgage_gbp == 82210.50


def test_loan_balances_exclude_personal_from_business_total() -> None:
    totals = compute_totals(
        [],
        [
            LiabilityView(1, "personal", "Lloyds 58315", "loan", 10923.14, 6.0, 200),
            LiabilityView(2, "personal", "Lloyds 6888", "loan", 11966.54, 6.0, 200),
            LiabilityView(3, "business", "Lloyds business", "loan", 12104.44, 6.0, 200),
        ],
    )
    assert totals.loan_gbp == 12104.44
    assert totals.personal_loan_gbp == round(10923.14 + 11966.54, 2)


def test_personal_credit_cards_exclude_business_cards() -> None:
    totals = compute_totals(
        [],
        [
            LiabilityView(1, "personal", "MBNA", "credit_card", 200, 22.9, 25),
            LiabilityView(2, "business", "Capital on Tap", "credit_card", 10748.98, 0, 0),
        ],
    )
    assert totals.credit_card_gbp == 10948.98
    assert totals.personal_credit_card_gbp == 200.0


def test_net_worth_does_not_double_count_linked_account_and_liability() -> None:
    totals = compute_totals(
        [
            AccountView(10, "personal", "current", "Current", 3000),
            AccountView(11, "personal", "credit_card", "MBNA", 800, credit_limit_gbp=2000),
        ],
        [
            LiabilityView(
                1,
                "personal",
                "MBNA",
                "credit_card",
                800,
                22.9,
                25,
                account_id=11,
            ),
        ],
    )
    assert totals.credit_card_gbp == 800
    assert totals.personal_debt_gbp == 800
    assert totals.available_credit_gbp == 1200
    assert totals.net_worth_gbp == 3000 - 800


def test_directors_loan_is_company_owes_director_and_omitted_from_net_worth() -> None:
    totals = compute_totals(
        [
            AccountView(1, "personal", "current", "Current", 1000),
            AccountView(2, "business", "current", "DLS", 5000),
            AccountView(3, "business", "directors_loan", "DLA", 2000),
        ],
        [
            LiabilityView(1, "business", "DLA", "directors_loan", 2000, 0, 0, account_id=3),
        ],
    )
    assert totals.directors_loan_gbp == 2000
    assert totals.personal_debt_gbp == 0
    assert totals.business_debt_gbp == 0
    assert totals.net_worth_gbp == 6000


def test_credit_limit_is_not_an_asset() -> None:
    totals = compute_totals(
        [AccountView(1, "personal", "credit_card", "Barclaycard", 400, credit_limit_gbp=2500)],
        [],
    )
    assert totals.available_credit_gbp == 2100
    assert totals.credit_limit_gbp == 2500
    assert totals.available_cash_gbp == 0
    assert totals.total_assets_gbp == 0
    assert totals.net_worth_gbp == -400


def test_overdraft_is_liability_not_cash() -> None:
    totals = compute_totals(
        [AccountView(1, "personal", "current", "Current", -350)],
        [],
    )
    assert totals.available_cash_gbp == 0
    assert totals.personal_overdraft_gbp == 350
    assert totals.net_worth_gbp == -350


def test_cashflow_surplus_from_snapshot() -> None:
    totals = compute_totals(
        [AccountView(1, "personal", "current", "Current", 1200)],
        [],
        SnapshotView(
            monthly_income_gbp=4000,
            monthly_spending_gbp=2500,
            household_bills_gbp=800,
            debt_repayments_gbp=200,
        ),
    )
    assert totals.monthly_surplus_gbp == 1300
    assert totals.cash_after_bills_gbp == 400


def test_cash_after_bills_nets_overdraft() -> None:
    totals = compute_totals(
        [
            AccountView(1, "personal", "current", "Current", 500),
            AccountView(2, "personal", "current", "Overdrawn", -200),
        ],
        [],
        SnapshotView(household_bills_gbp=100),
    )
    assert totals.personal_cash_gbp == 500
    assert totals.personal_overdraft_gbp == 200
    assert totals.cash_after_bills_gbp == 200


def test_credit_limit_is_zero_when_none_recorded() -> None:
    totals = compute_totals(
        [AccountView(1, "personal", "credit_card", "Barclaycard", 400)],
        [],
    )
    assert totals.credit_limit_gbp == 0
    assert totals.available_credit_gbp == 0


def test_recorded_credit_limit_is_separate_from_available() -> None:
    totals = compute_totals(
        [AccountView(1, "personal", "credit_card", "Barclaycard", 400, credit_limit_gbp=1000)],
        [],
    )
    assert totals.credit_limit_gbp == 1000
    assert totals.available_credit_gbp == 600


def test_available_credit_uses_debt_limit_when_no_account_limit() -> None:
    totals = compute_totals(
        [],
        [
            LiabilityView(
                1,
                "personal",
                "Barclaycard",
                "credit_card",
                400,
                22.9,
                25,
                credit_limit_gbp=1000,
            )
        ],
    )
    assert totals.credit_limit_gbp == 1000
    assert totals.available_credit_gbp == 600
    assert totals.credit_card_gbp == 400


def test_available_credit_uses_business_loan_debt_limit() -> None:
    totals = compute_totals(
        [],
        [
            LiabilityView(
                1,
                "business",
                "Capital on Tap",
                "business_loan",
                400,
                22.9,
                25,
                credit_limit_gbp=1000,
            )
        ],
    )
    assert totals.credit_limit_gbp == 1000
    assert totals.available_credit_gbp == 600


def test_available_credit_does_not_double_count_linked_card() -> None:
    totals = compute_totals(
        [AccountView(11, "personal", "credit_card", "MBNA", 800, credit_limit_gbp=2000)],
        [
            LiabilityView(
                1,
                "personal",
                "MBNA",
                "credit_card",
                800,
                22.9,
                25,
                account_id=11,
                credit_limit_gbp=2000,
            )
        ],
    )
    assert totals.available_credit_gbp == 1200
    assert totals.credit_limit_gbp == 2000


def test_debt_reduction_uses_original_balance_only() -> None:
    totals = compute_totals(
        [],
        [
            LiabilityView(
                1,
                "personal",
                "Loan",
                "loan",
                700,
                6,
                50,
                original_balance_gbp=1000,
            )
        ],
    )
    assert totals.debt_reduction_gbp == 300


def test_directors_loan_sides_use_explicit_direction() -> None:
    director_owes, company_owes = directors_loan_sides(
        [
            AccountView(
                1,
                "business",
                "directors_loan",
                "DLA",
                2500,
                dla_direction="director_owes_company",
            )
        ],
        [],
    )
    assert director_owes == 2500
    assert company_owes == 0


def test_external_debt_excludes_directors_loan_already_removed() -> None:
    assert external_debt_gbp(1000, 500, directors_loan=200) == 1500


def test_personal_and_company_positions_cancel_internal_loan() -> None:
    personal = personal_net_worth(
        personal_bank=4000,
        pension=10000,
        personal_external_debt=1000,
        company_owes_director=2000,
    )
    company = company_position(
        business_bank=8000,
        debtors=0,
        vat_reserve=500,
        corp_tax_reserve=300,
        business_external_debt=0,
        company_owes_director=2000,
    )
    assert personal == 15000
    assert company == 6800


def test_house_and_mortgage_move_personal_and_combined_not_business() -> None:
    """House (your half) £350k − mortgage £82,210.50 = +£267,789.50 personal and combined equity."""
    base_accounts = [
        AccountView(1, "personal", "current", "Current", 2000),
        AccountView(2, "business", "current", "Business", 5000),
        AccountView(3, "personal", "pension", "Pension", 10000),
    ]
    base_debts = [
        LiabilityView(1, "personal", "Card", "credit_card", 500, 20.0, 25),
        LiabilityView(2, "business", "Van finance", "loan", 1000, 8.0, 100),
    ]
    before = compute_totals(base_accounts, base_debts)
    after = compute_totals(
        [
            *base_accounts,
            AccountView(4, "personal", "property", "House (your half)", 350000),
        ],
        [
            *base_debts,
            LiabilityView(
                3,
                "personal",
                "House mortgage",
                "mortgage",
                82210.50,
                0.0,
                0,
            ),
        ],
    )

    def personal_from(totals):  # type: ignore[no-untyped-def]
        return personal_net_worth(
            personal_bank=round(totals.personal_cash_gbp - totals.personal_overdraft_gbp, 2),
            pension=totals.pension_gbp,
            personal_external_debt=totals.personal_debt_gbp,
            property_gbp=totals.property_gbp,
            other_assets_gbp=totals.other_assets_gbp,
        )

    def company_from(totals):  # type: ignore[no-untyped-def]
        return company_position(
            business_bank=round(totals.business_cash_gbp - totals.business_overdraft_gbp, 2),
            debtors=totals.debtors_gbp,
            vat_reserve=totals.vat_reserve_gbp,
            corp_tax_reserve=totals.corp_tax_reserve_gbp,
            business_external_debt=totals.business_debt_gbp,
        )

    assert after.property_gbp == 350000
    assert after.mortgage_gbp == 82210.50
    assert personal_from(after) - personal_from(before) == 267789.50
    assert after.net_worth_gbp - before.net_worth_gbp == 267789.50
    assert company_from(after) == company_from(before)
    assert after.business_debt_gbp == before.business_debt_gbp
    # House equity stays on the personal stack only.
    assert personal_from(after) == personal_from(before) + 350000 - 82210.50


def test_resolve_monthly_flow_prefers_snapshot_then_budget_over_open_banking() -> None:
    income, spending, _bills, _repay, source, configured = resolve_monthly_flow(
        snapshot_present=True,
        snapshot_income=3000,
        snapshot_spending=1200,
        open_banking_income=2800,
        open_banking_spending=900,
    )
    assert source == "snapshot"
    assert configured is True
    assert income == 3000
    income, spending, _bills, _repay, source, configured = resolve_monthly_flow(
        snapshot_present=False,
        open_banking_income=215.48,
        open_banking_spending=900,
        budget_income=5364,
        budget_spending=3892,
    )
    assert source == "budget"
    assert income == 5364
    income, spending, _bills, _repay, source, configured = resolve_monthly_flow(
        snapshot_present=False,
        open_banking_income=2800,
        open_banking_spending=900,
    )
    assert source == "open_banking"
    assert income == 2800
    assert spending == 900
    income, spending, bills, _repay, source, configured = resolve_monthly_flow(
        snapshot_present=False,
        cashflow_income=2500,
        cashflow_spending=800,
        cashflow_bills=400,
        budget_income=3000,
        budget_spending=900,
    )
    assert source == "cashflow"
    assert income == 2500
    assert spending == 800
    assert bills == 400
    income, spending, _bills, _repay, source, configured = resolve_monthly_flow(
        snapshot_present=False,
        budget_income=3100,
        budget_spending=950,
    )
    assert source == "budget"
    assert income == 3100
    assert spending == 950


def test_monthly_flow_note_labels_actual_vs_budget() -> None:
    from app.services.finance.finance_calc import monthly_flow_note

    assert "snapshot" in monthly_flow_note("snapshot").lower()
    assert "open banking" in monthly_flow_note("open_banking").lower()
    assert "budget plan" in monthly_flow_note("budget").lower()
    assert "not live" in monthly_flow_note("budget").lower()
    assert "no live" in monthly_flow_note("none").lower()
    assert "transfers excluded" in monthly_flow_note("transactions").lower()


def test_pick_open_banking_flow_uses_newest_nonempty_source() -> None:
    empty = MonthlyFlow()
    lunchflow = MonthlyFlow(income_gbp=1000, spending_gbp=200, as_of="2026-08-01T10:00:00+00:00")
    truelayer = MonthlyFlow(income_gbp=1800, spending_gbp=400, as_of="2026-08-15T10:00:00+00:00")
    assert pick_open_banking_flow(empty, empty).has_values() is False
    chosen = pick_open_banking_flow(lunchflow, empty)
    assert chosen.income_gbp == 1000
    chosen = pick_open_banking_flow(lunchflow, truelayer)
    assert chosen.income_gbp == 1800
    assert chosen.spending_gbp == 400


def test_previous_month_key_wraps_year() -> None:
    assert previous_month_key("2026-01") == "2025-12"
    assert previous_month_key("2026-08") == "2026-07"


def test_sandbox_open_banking_cash_is_excluded_from_totals() -> None:
    totals = compute_totals(
        [
            AccountView(1, "personal", "current", "Lloyds", 2000),
            AccountView(
                2,
                "personal",
                "current",
                "Mock ASPSP Current",
                9999,
                source="open_banking",
                provider="Mock ASPSP",
            ),
            AccountView(
                3,
                "business",
                "current",
                "Sandbox Current",
                5000,
                source="open_banking",
                provider="TrueLayer sandbox",
            ),
        ],
        [],
    )
    assert totals.personal_cash_gbp == 2000
    assert totals.business_cash_gbp == 0
    assert totals.available_cash_gbp == 2000


def test_null_interest_rate_known_is_treated_as_known() -> None:
    views = liabilities_from_schema(
        [
            SimpleNamespace(
                id=1,
                scope="personal",
                name="Legacy card",
                debt_type="credit_card",
                balance_gbp=1200,
                interest_rate_pct=12,
                minimum_payment_gbp=25,
                overpayment_gbp=0,
                account_id=None,
                original_balance_gbp=None,
                payment_day=None,
                dla_direction=None,
                interest_rate_known=None,
                credit_limit_gbp=None,
                is_active=True,
            )
        ]
    )
    assert views[0].interest_rate_known is True
    total, incomplete = monthly_interest_from_debts(views)
    assert incomplete is False
    assert total == 12.0


def test_vat_reserve_account_beats_snapshot_liability() -> None:
    """Live case: pot is £0.47; snapshot wrongly holds 2200+2202 liability."""
    totals = compute_totals(
        [AccountView(1, "business", "vat_reserve", "Vat Account", 0.47)],
        [],
        None,
        SnapshotView(vat_reserve_gbp=2956.27),
    )
    assert totals.vat_reserve_gbp == 0.47


def test_vat_account_used_when_snapshot_empty() -> None:
    totals = compute_totals(
        [AccountView(1, "business", "vat_reserve", "Vat Account", 400)],
        [],
        None,
        SnapshotView(),
    )
    assert totals.vat_reserve_gbp == 400.0


def test_snapshot_vat_reserve_used_when_no_vat_account() -> None:
    totals = compute_totals(
        [],
        [],
        None,
        SnapshotView(vat_reserve_gbp=500.0),
    )
    assert totals.vat_reserve_gbp == 500.0


def test_zero_vat_account_beats_snapshot_liability() -> None:
    totals = compute_totals(
        [AccountView(1, "business", "vat_reserve", "Vat Account", 0.0)],
        [],
        None,
        SnapshotView(vat_reserve_gbp=2956.27),
    )
    assert totals.vat_reserve_gbp == 0.0
