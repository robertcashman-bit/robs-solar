"""Overview side breakdowns: Defence Legal = QuickFile BS 1:1 when present."""

from app.services.finance.finance_calc import (
    AccountView,
    LiabilityView,
    build_overview_side_breakdowns,
    compute_totals,
    personal_net_worth,
)

# Live QuickFile Balance Sheet as at 01/09/2026 AFTER recode journal (GBP).
# 2300 Loans is gone; HP Finance 14,081.34; capital = 3,879.01.
_BS_0109_POST_RECODE = {
    "fixed_assets_gbp": 37183.24,
    "current_assets_gbp": 10469.99,
    "current_liabilities_gbp": 43774.22,
    "long_term_liabilities_gbp": 0.0,
    "capital_and_reserves_gbp": 3879.01,
    "asset_lines": [
        {"nominal_code": "1100", "label": "Debtors Control Account", "amount_gbp": 7597.31},
        {"nominal_code": "1200", "label": "Current Account", "amount_gbp": 0.11},
        {"nominal_code": "1210", "label": "VAT Account", "amount_gbp": 0.47},
        {
            "nominal_code": "2100",
            "label": "Creditors Control Account",
            "amount_gbp": 2391.83,
        },
        {"nominal_code": "2204", "label": "Manual Adjustments", "amount_gbp": 330.27},
        {"nominal_code": "2230", "label": "Pension Fund", "amount_gbp": 150.00},
    ],
    "liability_lines": [
        {"nominal_code": "50", "label": "HP Finance", "amount_gbp": 14081.34},
        {"nominal_code": "1201", "label": "Director's Loan", "amount_gbp": 7739.60},
        {
            "nominal_code": "1207",
            "label": "Lloyds Bank Business Account",
            "amount_gbp": 3448.22,
        },
        {"nominal_code": "1211", "label": "Holding", "amount_gbp": 6.00},
        {
            "nominal_code": "1258",
            "label": "Lloyds Bank Business Credit Card",
            "amount_gbp": 3310.63,
        },
        {"nominal_code": "1259", "label": "Capital on Tap", "amount_gbp": 11494.13},
        {"nominal_code": "2200", "label": "Sales Tax", "amount_gbp": 3070.93},
        {"nominal_code": "2202", "label": "VAT Liability", "amount_gbp": 623.37},
    ],
}

# Live QuickFile Balance Sheet as at 02/09/2026 (synced ~20:23 UTC).
# 2204 Manual Adj £330.27 + 2230 Pension £350 sit in liability LINES, but QF
# section totals count that £680.27 in current_assets (and out of CL). They are
# debit balances — Own, never Owe. Capital kept at 3465.90.
_BS_0209_LIVE = {
    "fixed_assets_gbp": 37183.24,
    "current_assets_gbp": 10959.95,
    "current_liabilities_gbp": 44677.29,
    "long_term_liabilities_gbp": 0.0,
    "capital_and_reserves_gbp": 3465.90,
    "asset_lines": [
        {"nominal_code": "1100", "label": "Debtors Control Account", "amount_gbp": 7597.31},
        {"nominal_code": "1200", "label": "Current Account", "amount_gbp": 0.11},
        {"nominal_code": "1210", "label": "VAT Account", "amount_gbp": 0.47},
        {
            "nominal_code": "2100",
            "label": "Creditors Control Account",
            "amount_gbp": 2391.83,
        },
        {"nominal_code": "2300", "label": "Loans", "amount_gbp": 289.96},
    ],
    "liability_lines": [
        {"nominal_code": "50", "label": "HP Finance", "amount_gbp": 14081.34},
        {"nominal_code": "1201", "label": "Director's Loan", "amount_gbp": 7739.60},
        {
            "nominal_code": "1207",
            "label": "Lloyds Bank Business Account",
            "amount_gbp": 4351.29,
        },
        {"nominal_code": "1211", "label": "Holding", "amount_gbp": 6.00},
        {
            "nominal_code": "1258",
            "label": "Lloyds Bank Business Credit Card",
            "amount_gbp": 3310.63,
        },
        {"nominal_code": "1259", "label": "Capital on Tap", "amount_gbp": 11494.13},
        {"nominal_code": "2200", "label": "Sales Tax", "amount_gbp": 3070.93},
        {"nominal_code": "2202", "label": "VAT Liability", "amount_gbp": 623.37},
        {"nominal_code": "2204", "label": "Manual Adjustments", "amount_gbp": 330.27},
        {"nominal_code": "2230", "label": "Pension Fund", "amount_gbp": 350.00},
    ],
}


def _labels(lines, *, tier: str | None = None) -> set[str]:
    return {
        line.label
        for line in lines
        if tier is None or line.tier == tier
    }


def _amount(lines, label: str) -> float:
    return next(line.amount_gbp for line in lines if line.label == label)


def test_personal_owed_primary_lists_mortgage_cards_loans_od() -> None:
    accounts = [
        AccountView(1, "personal", "current", "Current", -200.0),
        AccountView(2, "personal", "property", "House (your half)", 350000.0),
        AccountView(3, "personal", "pension", "Pension", 50000.0),
    ]
    debts = [
        LiabilityView(1, "personal", "House mortgage", "mortgage", 82210.5, 0.0, 0.0),
        LiabilityView(2, "personal", "Amex", "credit_card", 1200.0, 20.0, 50.0),
        LiabilityView(3, "personal", "Car loan", "loan", 4000.0, 8.0, 200.0),
    ]
    totals = compute_totals(accounts, debts)
    personal_nw = personal_net_worth(
        personal_bank=round(totals.personal_cash_gbp - totals.personal_overdraft_gbp, 2),
        pension=totals.pension_gbp,
        personal_external_debt=totals.personal_debt_gbp,
        property_gbp=totals.property_gbp,
        other_assets_gbp=totals.other_assets_gbp,
    )
    personal, _business = build_overview_side_breakdowns(
        totals=totals,
        accounts=accounts,
        liabilities=debts,
        director_owes_company=0.0,
        company_owes_director=0.0,
        personal_whats_left=personal_nw,
        mortgage_configured=True,
        pension_configured=True,
    )
    primary = _labels(personal.owed, tier="primary")
    assert "House mortgage" in primary
    assert "Credit cards" in primary
    assert "Loans" in primary
    assert "Overdraft" in primary
    assert all(line.tier == "primary" for line in personal.owed)
    mortgage = next(line for line in personal.owed if line.key == "mortgage")
    assert mortgage.amount_gbp == 82210.5
    assert "164,421" in (mortgage.hint or "")
    assert round(personal.owned_total_gbp - personal.owed_total_gbp, 2) == personal.whats_left_gbp


def test_business_whats_left_uses_capital_when_bs_present() -> None:
    accounts = [
        AccountView(1, "business", "current", "Lloyds business", -6290.0),
        AccountView(2, "personal", "current", "Current", 2000.0),
    ]
    debts = [
        LiabilityView(1, "business", "Tesla Model 3 HP AF-63591", "loan", 13000.0, 0.0, 766.0),
        LiabilityView(2, "business", "Trade creditors", "other", 5000.0, 0.0, 0.0),
    ]
    totals = compute_totals(accounts, debts)
    personal_nw = personal_net_worth(
        personal_bank=2000.0,
        pension=0.0,
        personal_external_debt=0.0,
    )
    personal, business = build_overview_side_breakdowns(
        totals=totals,
        accounts=accounts,
        liabilities=[
            *debts,
            LiabilityView(
                3,
                "business",
                "Directors loan",
                "directors_loan",
                9037.0,
                0.0,
                0.0,
                dla_direction="company_owes_director",
            ),
        ],
        director_owes_company=0.0,
        company_owes_director=9037.0,
        personal_whats_left=personal_nw,
        mortgage_configured=False,
        pension_configured=False,
        balance_sheet={
            "fixed_assets_gbp": 18000.0,
            "current_assets_gbp": 4500.0,
            "current_liabilities_gbp": 12000.0,
            "long_term_liabilities_gbp": 13000.0,
            "capital_and_reserves_gbp": -2500.0,
            # Minimal lines — register must NOT fill Tesla / cards on top.
            "asset_lines": [
                {"nominal_code": "1200", "label": "Current Account", "amount_gbp": 4500.0},
            ],
            "liability_lines": [
                {"nominal_code": "50", "label": "HP Finance", "amount_gbp": 13000.0},
                {
                    "nominal_code": "1201",
                    "label": "Director's Loan",
                    "amount_gbp": 9037.0,
                },
                {"nominal_code": "1207", "label": "Overdraft", "amount_gbp": 2963.0},
            ],
        },
    )
    tesla = next(line for line in business.owed if "Tesla" in line.label)
    assert tesla.tier == "primary"
    assert tesla.amount_gbp == 13000.0
    dla = next(line for line in business.owed if line.key == "company_owes_robert_biz")
    assert dla.tier == "primary"
    fixed = next(line for line in business.owned if line.key == "fixed_assets")
    assert fixed.label == "Vehicles and kit"
    assert fixed.amount_gbp == 18000.0
    assert fixed.tier == "primary"
    assert business.whats_left_available is True
    assert business.whats_left_gbp == -2500.0
    assert "balance sheet" in business.whats_left_hint.lower()
    # Old working-capital −£35k path must not appear when BS is present.
    assert business.whats_left_gbp != round(
        totals.business_cash_gbp
        - totals.business_overdraft_gbp
        + totals.debtors_gbp
        - totals.business_debt_gbp
        - 9037.0,
        2,
    )
    assert "Car value not on this list" not in _labels(business.owned)
    # Register must not add a second Credit cards / Loans lump.
    assert "Credit cards" not in _labels(business.owed)
    assert round(business.owned_total_gbp - business.owed_total_gbp, 2) == business.whats_left_gbp


def test_dls_0109_post_recode_balance_sheet_is_plain_english_one_to_one() -> None:
    """Live 01/09/2026 AFTER recode: QF lines only — no register, no 2300."""
    accounts = [
        AccountView(1, "business", "current", "Lloyds business", -3448.22),
    ]
    # Stale / parallel register — must be ignored while BS is present.
    debts = [
        LiabilityView(
            1,
            "business",
            "Tesla Model 3 HP AF-63591",
            "loan",
            18018.09,
            0.0,
            766.0,
        ),
        LiabilityView(
            2,
            "business",
            "Capital on Tap",
            "loan",
            11494.13,
            0.0,
            0.0,
        ),
        LiabilityView(
            3,
            "business",
            "Lloyds card",
            "credit_card",
            3310.63,
            0.0,
            0.0,
        ),
        # If CoT were miscategorised as a card, old code lumped ~£14k.
        LiabilityView(
            5,
            "business",
            "Extra card",
            "credit_card",
            9999.0,
            0.0,
            0.0,
        ),
        # Do not invent Funding Circle as a remaining loan from register.
        LiabilityView(
            6,
            "business",
            "Funding Circle",
            "business_loan",
            12000.0,
            0.0,
            0.0,
        ),
    ]
    totals = compute_totals(accounts, debts)
    _personal, business = build_overview_side_breakdowns(
        totals=totals,
        accounts=accounts,
        liabilities=[
            *debts,
            LiabilityView(
                4,
                "business",
                "Directors loan",
                "directors_loan",
                7739.60,
                0.0,
                0.0,
                dla_direction="company_owes_director",
            ),
        ],
        director_owes_company=0.0,
        company_owes_director=7739.60,
        personal_whats_left=0.0,
        mortgage_configured=False,
        pension_configured=False,
        balance_sheet=_BS_0109_POST_RECODE,
    )

    # What's left = capital & reserves from the Defence Legal balance sheet.
    assert business.whats_left_gbp == 3879.01
    assert business.whats_left_available is True
    assert "balance sheet" in business.whats_left_hint.lower()

    # Own: FA total + CA lines (plain English). Bank = 1200 only, not net of OD.
    assert _amount(business.owned, "Vehicles and kit") == 37183.24
    assert _amount(business.owned, "Customers still to pay") == 7597.31
    assert _amount(business.owned, "Bank") == 0.11
    assert _amount(business.owned, "Other company money") == 2391.83
    assert _amount(business.owned, "VAT account") == 0.47
    assert _amount(business.owned, "Manual adjustments") == 330.27
    assert _amount(business.owned, "Pension fund") == 150.00
    # 2300 is gone after the recode journal — do not invent Funding Circle.
    assert "Loan repayments" not in " ".join(_labels(business.owned))
    assert "Funding Circle" not in " ".join(
        (line.hint or "") + " " + line.label for line in business.owned + business.owed
    )
    assert "Suppliers still to pay" not in _labels(business.owned) | _labels(business.owed)

    # Owe: each QF liability once — Capital on Tap and Lloyds card split.
    assert _amount(business.owed, "Tesla still to pay") == 14081.34
    assert _amount(business.owed, "Overdraft") == 3448.22
    assert _amount(business.owed, "Lloyds card") == 3310.63
    assert _amount(business.owed, "Capital on Tap") == 11494.13
    assert _amount(business.owed, "Company still owes Robert") == 7739.60
    assert _amount(business.owed, "VAT") == round(3070.93 + 623.37, 2)
    # Holding £6 sits in More — not folded into VAT, not inventing FC.
    holding = next(line for line in business.owed if line.key == "holding")
    assert holding.amount_gbp == 6.00
    assert holding.tier == "more"

    owed_labels = [line.label for line in business.owed]
    assert owed_labels.count("Credit cards") == 0
    assert owed_labels.count("Loans") == 0
    assert owed_labels.count("Other amounts owed") == 0
    assert owed_labels.count("Unnamed QuickFile creditors") == 0
    assert owed_labels.count("Other QuickFile creditors") == 0
    assert owed_labels.count("Funding Circle") == 0
    assert len([line for line in business.owed if "Tesla" in line.label]) == 1
    # No invented Tesla market value on the own side; car = 0010 NBV via FA total.
    assert not any(
        line.amount_gbp is not None and abs(float(line.amount_gbp) - 43054.85) < 0.01
        for line in business.owned
    )
    # 2300 must never appear as a debt; Tesla is 0050 only.
    assert not any(
        line.kind == "debt"
        and line.amount_gbp is not None
        and abs(float(line.amount_gbp) - 27720.15) < 0.01
        for line in business.owed
    )
    # Leftover stays QF capital (post-recode £3,879.01).
    assert business.whats_left_gbp == 3879.01
    # Identity: FA+CA − CL−LTL = capital within 1p.
    assert business.owned_total_gbp == round(37183.24 + 10469.99, 2)
    assert business.owed_total_gbp == 43774.22
    assert abs(
        round(business.owned_total_gbp - business.owed_total_gbp, 2)
        - business.whats_left_gbp
    ) <= 0.01
    # Register extras (£9999 card, stale Tesla, Funding Circle) must not inflate.
    assert business.owed_total_gbp < 45000
    assert business.owned_total_gbp == 47653.23


def test_dls_0209_prepaid_2204_2230_on_own_not_owe() -> None:
    """Live 02/09/2026: 2204+2230 in liability lines are Own; leftover stays capital."""
    accounts = [
        AccountView(1, "business", "current", "Lloyds business", -4351.29),
    ]
    debts = [
        LiabilityView(
            1,
            "business",
            "Tesla Model 3 HP AF-63591",
            "loan",
            18018.09,
            0.0,
            766.0,
        ),
    ]
    totals = compute_totals(accounts, debts)
    _personal, business = build_overview_side_breakdowns(
        totals=totals,
        accounts=accounts,
        liabilities=debts,
        director_owes_company=0.0,
        company_owes_director=7739.60,
        personal_whats_left=0.0,
        mortgage_configured=False,
        pension_configured=False,
        balance_sheet=_BS_0209_LIVE,
    )

    # What's left = official capital & reserves (do not change leftover).
    assert business.whats_left_gbp == 3465.90
    assert business.whats_left_available is True

    # Official pile headers.
    assert business.owned_total_gbp == round(37183.24 + 10959.95, 2)
    assert business.owed_total_gbp == 44677.29
    assert abs(
        round(business.owned_total_gbp - business.owed_total_gbp, 2)
        - business.whats_left_gbp
    ) <= 0.01

    # 2204 / 2230 on Own under real names — never Owe, never ghost plug.
    assert _amount(business.owned, "Manual adjustments") == 330.27
    assert _amount(business.owned, "Pension fund") == 350.00
    assert "Manual adjustments" not in _labels(business.owed)
    assert "Pension fund" not in _labels(business.owed)
    assert not any(line.key == "bs_other_owned" for line in business.owned)
    assert not any(
        abs(float(line.amount_gbp or 0) - 680.27) < 0.01
        for line in business.owned
        if line.label == "Other company money"
    )
    # 2100 debit stays "Other company money" (unallocated supplier payments).
    other_money = [
        line
        for line in business.owned
        if line.label == "Other company money"
    ]
    assert len(other_money) == 1
    assert other_money[0].amount_gbp == 2391.83
    assert other_money[0].key == "creditors_debit"

    # 2300 = loan repayments on the books (asset), not a Tesla/loan balance.
    assert _amount(business.owned, "Loan repayments (on the books as an asset)") == 289.96

    # Named owe lines; Tesla from 0050 only.
    assert _amount(business.owed, "Tesla still to pay") == 14081.34
    assert _amount(business.owed, "Overdraft") == 4351.29
    assert _amount(business.owed, "Lloyds card") == 3310.63
    assert _amount(business.owed, "Capital on Tap") == 11494.13
    assert _amount(business.owed, "Company still owes Robert") == 7739.60
    assert _amount(business.owed, "VAT") == round(3070.93 + 623.37, 2)
    holding = next(line for line in business.owed if line.key == "holding")
    assert holding.amount_gbp == 6.00
    assert holding.tier == "more"
    assert len([line for line in business.owed if "Tesla" in line.label]) == 1


def test_business_without_balance_sheet_shows_gap_not_working_capital() -> None:
    accounts = [AccountView(1, "business", "current", "Lloyds", -6290.0)]
    debts = [
        LiabilityView(1, "business", "Tesla Model 3 HP", "loan", 13000.0, 0.0, 766.0),
    ]
    totals = compute_totals(accounts, debts)
    _personal, business = build_overview_side_breakdowns(
        totals=totals,
        accounts=accounts,
        liabilities=debts,
        director_owes_company=0.0,
        company_owes_director=0.0,
        personal_whats_left=0.0,
        mortgage_configured=False,
        pension_configured=False,
        balance_sheet=None,
    )
    assert business.whats_left_available is False
    assert business.whats_left_gbp is None
    assert "Balance sheet not synced" in business.whats_left_hint
    assert any(line.key == "bs_missing" for line in business.owned)
    tesla = next(line for line in business.owed if "Tesla" in line.label)
    assert tesla.tier == "primary"
    # Register fallback is allowed only when BS is missing.
    assert tesla.amount_gbp == 13000.0


def test_personal_and_business_lines_stay_unmixed() -> None:
    accounts = [
        AccountView(1, "personal", "current", "Current", 1000.0),
        AccountView(2, "business", "current", "Biz", 2000.0),
    ]
    debts = [
        LiabilityView(1, "personal", "Personal loan", "loan", 400.0, 10.0, 50.0),
        LiabilityView(2, "business", "Van finance", "loan", 900.0, 8.0, 100.0),
    ]
    totals = compute_totals(accounts, debts)
    personal_nw = personal_net_worth(
        personal_bank=1000.0,
        pension=0.0,
        personal_external_debt=totals.personal_debt_gbp,
    )
    personal, business = build_overview_side_breakdowns(
        totals=totals,
        accounts=accounts,
        liabilities=debts,
        director_owes_company=0.0,
        company_owes_director=0.0,
        personal_whats_left=personal_nw,
        mortgage_configured=False,
        pension_configured=False,
    )
    assert "Loans" in _labels(personal.owed, tier="primary")
    assert "House share" not in _labels(business.owned)
    assert personal.owed_total_gbp == 400.0


def test_expensive_apr_hint_on_personal_cards_is_plain_english() -> None:
    accounts = [AccountView(1, "personal", "current", "Current", 500.0)]
    debts = [
        LiabilityView(1, "personal", "Amex", "credit_card", 1200.0, 22.9, 50.0),
        LiabilityView(2, "personal", "Barclaycard", "credit_card", 400.0, 12.0, 25.0),
    ]
    totals = compute_totals(accounts, debts)
    personal, _ = build_overview_side_breakdowns(
        totals=totals,
        accounts=accounts,
        liabilities=debts,
        director_owes_company=0.0,
        company_owes_director=0.0,
        personal_whats_left=500.0 - totals.personal_debt_gbp,
        mortgage_configured=False,
        pension_configured=False,
    )
    cards = next(line for line in personal.owed if line.key == "personal_cards")
    assert "Most expensive APR" in (cards.hint or "")
    assert "Amex" in (cards.hint or "")
    assert "22.9%" in (cards.hint or "")


def test_capital_on_tap_stays_on_dls_not_personal() -> None:
    accounts = [
        AccountView(1, "personal", "current", "Current", 1000.0),
        AccountView(2, "business", "current", "Biz", 0.0),
    ]
    debts = [
        LiabilityView(
            1, "business", "Capital on Tap", "business_loan", 11494.13, 0.0, 0.0
        ),
        LiabilityView(2, "personal", "Amex", "credit_card", 800.0, 20.0, 40.0),
    ]
    totals = compute_totals(accounts, debts)
    personal, business = build_overview_side_breakdowns(
        totals=totals,
        accounts=accounts,
        liabilities=debts,
        director_owes_company=0.0,
        company_owes_director=0.0,
        personal_whats_left=1000.0 - 800.0,
        mortgage_configured=False,
        pension_configured=False,
        balance_sheet=_BS_0109_POST_RECODE,
    )
    assert "Capital on Tap" not in _labels(personal.owed)
    assert any("Capital on Tap" in label for label in _labels(business.owed))
    assert personal.owed_total_gbp == 800.0
