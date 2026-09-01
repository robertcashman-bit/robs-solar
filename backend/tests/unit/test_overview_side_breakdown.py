"""Overview side breakdowns keep formula totals and surface vehicle HP gaps."""

from app.services.finance.finance_calc import (
    AccountView,
    LiabilityView,
    build_overview_side_breakdowns,
    company_position,
    compute_totals,
    personal_net_worth,
)


def test_tesla_hp_without_car_asset_surfaces_gap_not_invented_value() -> None:
    accounts = [
        AccountView(1, "business", "current", "Lloyds business", 0.0),
        AccountView(2, "personal", "current", "Current", 2000.0),
        AccountView(3, "personal", "property", "House (your half)", 350000.0),
        AccountView(4, "personal", "pension", "Pension", 50000.0),
    ]
    debts = [
        LiabilityView(1, "business", "Tesla Model 3 HP AF-63591", "loan", 13000.0, 0.0, 766.0),
        LiabilityView(2, "business", "Other creditors", "other", 5000.0, 0.0, 0.0),
        LiabilityView(3, "personal", "House mortgage", "mortgage", 82210.5, 0.0, 0.0),
    ]
    # Simulate overdrawn business bank via negative current handled in compute_totals.
    accounts_od = [
        AccountView(1, "business", "current", "Lloyds business", -6290.0),
        *accounts[1:],
    ]
    totals = compute_totals(accounts_od, debts)
    director_owes, company_owes = 0.0, 9037.0
    personal_bank = round(totals.personal_cash_gbp - totals.personal_overdraft_gbp, 2)
    business_bank = round(totals.business_cash_gbp - totals.business_overdraft_gbp, 2)
    personal_nw = personal_net_worth(
        personal_bank=personal_bank,
        pension=totals.pension_gbp,
        personal_external_debt=totals.personal_debt_gbp,
        property_gbp=totals.property_gbp,
        other_assets_gbp=totals.other_assets_gbp,
        company_owes_director=company_owes,
    )
    company_pos = company_position(
        business_bank=business_bank,
        debtors=totals.debtors_gbp,
        vat_reserve=totals.vat_reserve_gbp,
        corp_tax_reserve=totals.corp_tax_reserve_gbp,
        business_external_debt=totals.business_debt_gbp,
        company_owes_director=company_owes,
    )
    personal, business = build_overview_side_breakdowns(
        totals=totals,
        accounts=accounts_od,
        liabilities=[
            *debts,
            LiabilityView(
                4,
                "business",
                "Directors loan",
                "directors_loan",
                company_owes,
                0.0,
                0.0,
                dla_direction="company_owes_director",
            ),
        ],
        director_owes_company=director_owes,
        company_owes_director=company_owes,
        personal_whats_left=personal_nw,
        business_whats_left=company_pos,
        mortgage_configured=True,
        pension_configured=True,
    )

    assert personal.whats_left_gbp == personal_nw
    assert business.whats_left_gbp == company_pos
    assert round(business.owned_total_gbp - business.owed_total_gbp, 2) == company_pos

    gap = next(line for line in business.owned if line.key == "car_gap")
    assert gap.label == "Car value not on this list"
    assert gap.amount_gbp is None
    assert gap.tier == "primary"

    tesla = next(line for line in business.owed if "tesla" in line.label.lower() or "Tesla" in line.label)
    assert tesla.label == "Tesla still to pay"
    assert tesla.tier == "more"
    assert tesla.amount_gbp == 13000.0

    dla = next(line for line in business.owed if line.key == "company_owes_robert_biz")
    assert dla.label == "Company still owes Robert"
    assert dla.tier == "more"

    # No invented car asset amount anywhere.
    assert all(line.amount_gbp != 25000 for line in business.owned)


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
    company_pos = company_position(
        business_bank=2000.0,
        debtors=0.0,
        vat_reserve=0.0,
        corp_tax_reserve=0.0,
        business_external_debt=totals.business_debt_gbp,
    )
    personal, business = build_overview_side_breakdowns(
        totals=totals,
        accounts=accounts,
        liabilities=debts,
        director_owes_company=0.0,
        company_owes_director=0.0,
        personal_whats_left=personal_nw,
        business_whats_left=company_pos,
        mortgage_configured=False,
        pension_configured=False,
    )
    personal_labels = {line.label for line in (*personal.owned, *personal.owed)}
    business_labels = {line.label for line in (*business.owned, *business.owed)}
    assert "Personal loan" not in business_labels
    assert "Van finance" not in personal_labels or "Loans" in business_labels
    assert "House share" not in business_labels
