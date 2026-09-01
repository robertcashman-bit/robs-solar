"""Overview side breakdowns: Defence Legal = QuickFile BS 1:1 when present."""

from app.services.finance.finance_calc import (
    AccountView,
    LiabilityView,
    build_overview_side_breakdowns,
    compute_totals,
    personal_net_worth,
)

# Live QuickFile Balance Sheet as at 01/09/2026 (GBP) — confirmed on screen.
_BS_0109 = {
    "fixed_assets_gbp": 37183.24,
    "current_assets_gbp": 38190.14,
    "current_liabilities_gbp": 45335.82,
    "long_term_liabilities_gbp": 0.0,
    "capital_and_reserves_gbp": 30037.56,
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
        {"nominal_code": "2300", "label": "Loans", "amount_gbp": 27720.15},
    ],
    "liability_lines": [
        {"nominal_code": "50", "label": "HP Finance", "amount_gbp": 15642.94},
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


def test_dls_0109_balance_sheet_is_plain_english_one_to_one() -> None:
    """Live 01/09/2026 sheet: QF lines only — no register double-count."""
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
        balance_sheet=_BS_0109,
    )

    # What's left = capital & reserves.
    assert business.whats_left_gbp == 30037.56
    assert business.whats_left_available is True
    assert "balance sheet" in business.whats_left_hint.lower()

    # Own: FA total + CA lines (plain English).
    assert _amount(business.owned, "Vehicles and kit") == 37183.24
    assert _amount(business.owned, "Customers still to pay") == 7597.31
    assert _amount(business.owned, "Bank") == 0.11
    assert _amount(business.owned, "Loans outstanding") == 27720.15
    # 2100 debit is other company money — never "Suppliers still to pay".
    assert _amount(business.owned, "Other company money") == 2391.83
    assert "Suppliers still to pay" not in _labels(business.owned) | _labels(business.owed)

    # Owe: each QF liability once — Capital on Tap and Lloyds card split.
    assert _amount(business.owed, "Tesla still to pay") == 15642.94
    assert _amount(business.owed, "Overdraft") == 3448.22
    assert _amount(business.owed, "Lloyds card") == 3310.63
    assert _amount(business.owed, "Capital on Tap") == 11494.13
    assert _amount(business.owed, "Company still owes Robert") == 7739.60
    assert _amount(business.owed, "VAT") == round(3070.93 + 623.37 + 6.00, 2)

    owed_labels = [line.label for line in business.owed]
    owned_labels = [line.label for line in business.owned]
    assert owed_labels.count("Credit cards") == 0
    assert owed_labels.count("Loans") == 0  # CoT is its own line; 2300 is own-side
    assert owed_labels.count("Other amounts owed") == 0
    assert owed_labels.count("Unnamed QuickFile creditors") == 0
    assert owed_labels.count("Other QuickFile creditors") == 0
    assert "Loans outstanding" in owned_labels
    assert len([line for line in business.owed if "Tesla" in line.label]) == 1
    # No invented Tesla market value on the own side.
    assert not any(
        line.amount_gbp is not None and abs(float(line.amount_gbp) - 43054.85) < 0.01
        for line in business.owned
    )
    # 2300 must never appear as a debt.
    assert not any(
        line.kind == "debt"
        and line.amount_gbp is not None
        and abs(float(line.amount_gbp) - 27720.15) < 0.01
        for line in business.owed
    )
    # Identity: FA+CA − CL−LTL = capital within 1p.
    assert business.owned_total_gbp == round(37183.24 + 38190.14, 2)
    assert business.owed_total_gbp == 45335.82
    assert abs(
        round(business.owned_total_gbp - business.owed_total_gbp, 2)
        - business.whats_left_gbp
    ) <= 0.01
    # Register extras (£9999 card, stale Tesla) must not inflate totals.
    assert business.owed_total_gbp < 50000


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
