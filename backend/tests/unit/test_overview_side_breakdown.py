"""Overview side breakdowns: primary debts + QuickFile Capital and reserves."""

from app.services.finance.finance_calc import (
    AccountView,
    LiabilityView,
    build_overview_side_breakdowns,
    compute_totals,
    personal_net_worth,
)


def _labels(lines, *, tier: str | None = None) -> set[str]:
    return {
        line.label
        for line in lines
        if tier is None or line.tier == tier
    }


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


def test_business_tesla_hp_is_primary_and_whats_left_uses_capital() -> None:
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


def test_business_qf_hp_loans_map_to_tesla_one_plug_only() -> None:
    """Live 01/09/2026 shape: Tesla from 0050; 2300 is an OWN-side asset, not HP."""
    accounts = [
        AccountView(1, "business", "current", "Lloyds business", -3448.22),
    ]
    # Stale register remaining capital — must lose to live QF HP Finance.
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
        balance_sheet={
            "fixed_assets_gbp": 37183.24,
            "current_assets_gbp": 38190.14,
            "current_liabilities_gbp": 45335.82,
            "long_term_liabilities_gbp": 0.0,
            "capital_and_reserves_gbp": 30037.56,
            "asset_lines": [
                {"nominal_code": "1200", "label": "Current", "amount_gbp": 0.11},
                {
                    "nominal_code": "2100",
                    "label": "Creditors Control Account",
                    "amount_gbp": 2391.83,
                },
                {"nominal_code": "2300", "label": "Loans", "amount_gbp": 27720.15},
            ],
            "liability_lines": [
                {"nominal_code": "50", "label": "HP Finance", "amount_gbp": 15642.94},
                {
                    "nominal_code": "1201",
                    "label": "Director's Loan",
                    "amount_gbp": 7739.60,
                },
                {"nominal_code": "1207", "label": "Overdraft", "amount_gbp": 3448.22},
                {"nominal_code": "1258", "label": "Lloyds card", "amount_gbp": 3310.63},
                {
                    "nominal_code": "1259",
                    "label": "Capital on Tap",
                    "amount_gbp": 11494.13,
                },
                {"nominal_code": "2200", "label": "VAT Liability", "amount_gbp": 3070.93},
                {"nominal_code": "2202", "label": "VAT", "amount_gbp": 623.37},
            ],
        },
    )
    owed_labels = [line.label for line in business.owed]
    owned_labels = [line.label for line in business.owned]
    assert owed_labels.count("Other amounts owed") == 0
    assert "Loans outstanding" in owned_labels
    loans_asset = next(line for line in business.owned if line.key == "qf_loans_asset")
    assert loans_asset.amount_gbp == 27720.15
    tesla_lines = [line for line in business.owed if "Tesla" in line.label]
    assert len(tesla_lines) == 1
    # Live QF HP Finance remaining capital — not stale register £18k, not 60×£766.
    assert tesla_lines[0].amount_gbp == 15642.94
    assert owed_labels.count("Unnamed QuickFile creditors") <= 1
    assert business.whats_left_gbp == 30037.56
    assert business.whats_left_available is True
    # 2300 must never appear as a second car-sized owed plug.
    assert not any(
        line.kind == "debt"
        and line.amount_gbp is not None
        and abs(float(line.amount_gbp) - 27720.15) < 0.01
        for line in business.owed
    )

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
