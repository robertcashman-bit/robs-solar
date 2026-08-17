"""Unit tests for statement parsers, history stats, safe-to-spend, transfers."""

from __future__ import annotations

from app.services.finance.finance_calc import FinanceTotals, LiabilityView, SnapshotView
from app.services.finance.finance_categoriser_service import finance_categoriser_service
from app.services.finance.finance_history_stats import (
    classify_volatility,
    median_gbp,
    remove_outliers,
    trimmed_mean_gbp,
)
from app.services.finance.finance_safe_spend_service import compute_safe_to_spend
from app.services.finance.statement_parsers import (
    guess_column_mapping,
    parse_csv_text,
    parse_ofx_text,
    parse_qif_text,
    parse_statement_bytes,
)


def test_csv_column_guess_and_parse() -> None:
    text = (
        "Transaction Date,Narrative,Paid out,Paid in\n"
        "01/02/2024,TESCO STORES,45.20,\n"
        "02/02/2024,SALARY,,2500.00\n"
    )
    mapping = guess_column_mapping(["Transaction Date", "Narrative", "Paid out", "Paid in"])
    assert mapping["posted_on"] == "Transaction Date"
    parsed = parse_csv_text(text, account_name="Current", scope="personal")
    assert parsed["format"] == "csv"
    assert len(parsed["rows"]) == 2
    assert parsed["rows"][0]["amount_gbp"] == -45.2
    assert parsed["rows"][1]["amount_gbp"] == 2500.0


def test_uk_slash_date_stays_on_the_same_calendar_day() -> None:
    text = "Date,Description,Amount\n01/08/2026,TESCO,-12.00\n31/08/2026,RENT,-800.00\n"
    parsed = parse_csv_text(text, account_name="Current", scope="personal")
    assert [row["posted_on"] for row in parsed["rows"]] == ["2026-08-01", "2026-08-31"]


def test_ofx_and_qif_parse() -> None:
    ofx = """
    <OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
    <STMTTRN><DTPOSTED>20240315</DTPOSTED><TRNAMT>-12.50</TRNAMT><NAME>COFFEE</NAME><FITID>1</FITID></STMTTRN>
    </BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
    """
    ofx_rows = parse_ofx_text(ofx, account_name="Current")
    assert len(ofx_rows["rows"]) == 1
    assert ofx_rows["rows"][0]["posted_on"] == "2024-03-15"

    qif = "!Type:Bank\nD15/03/2024\nT-10.00\nPNetflix\n^\n"
    qif_rows = parse_qif_text(qif, account_name="Current")
    assert len(qif_rows["rows"]) == 1
    assert "Netflix" in qif_rows["rows"][0]["description"]


def test_parse_statement_bytes_detects_format() -> None:
    result = parse_statement_bytes(
        b"Date,Description,Amount\n2024-01-01,Test,-1.00\n",
        "bank.csv",
        account_name="A",
        scope="business",
    )
    assert result["format"] == "csv"
    assert result["rows"][0]["scope"] == "business"


def test_median_outliers_and_volatility() -> None:
    values = [100.0, 110.0, 105.0, 500.0, 95.0, 102.0, 98.0, 101.0]
    kept, outliers = remove_outliers(values)
    assert 500.0 in outliers
    assert len(kept) < len(values)
    assert median_gbp([10, 20, 30]) == 20.0
    assert trimmed_mean_gbp([10, 20, 30, 40, 1000]) < 300
    assert classify_volatility(0.05, recurring=True) == "FIXED"
    assert classify_volatility(1.5, recurring=False) == "EXCEPTIONAL"


def test_categoriser_tesla_and_transfer() -> None:
    hit = finance_categoriser_service.categorise_description(
        "TESLA FINANCE PLC", scope="business"
    )
    assert hit["category"] == "Vehicle finance"
    assert finance_categoriser_service.looks_like_transfer("FASTER PAYMENT TO SAVINGS")


def test_safe_to_spend_breakdown_transparent() -> None:
    totals = FinanceTotals(
        personal_cash_gbp=2000,
        business_cash_gbp=5000,
        available_cash_gbp=7000,
        personal_overdraft_gbp=0,
        business_overdraft_gbp=0,
        available_credit_gbp=0,
        credit_limit_gbp=0,
        pension_gbp=0,
        property_gbp=0,
        other_assets_gbp=0,
        debtors_gbp=0,
        total_assets_gbp=7000,
        personal_debt_gbp=1000,
        business_debt_gbp=2000,
        credit_card_gbp=1000,
        loan_gbp=2000,
        mortgage_gbp=0,
        directors_loan_gbp=0,
        creditors_gbp=0,
        vat_reserve_gbp=400,
        corp_tax_reserve_gbp=800,
        total_liabilities_gbp=3000,
        net_worth_gbp=4000,
        monthly_income_gbp=3000,
        monthly_spending_gbp=1500,
        monthly_surplus_gbp=1500,
        cash_after_bills_gbp=1000,
        vat_reserve_warning=False,
        corp_tax_reserve_warning=False,
        debt_reduction_gbp=0,
    )
    personal = SnapshotView(
        monthly_income_gbp=3000,
        monthly_spending_gbp=1500,
        household_bills_gbp=900,
        debt_repayments_gbp=200,
    )
    business = SnapshotView(turnover_gbp=8000, expenses_gbp=4000)
    liabilities = [
        LiabilityView(
            id=1,
            scope="personal",
            name="Card",
            debt_type="credit_card",
            balance_gbp=1000,
            interest_rate_pct=20,
            minimum_payment_gbp=50,
            is_active=True,
        ),
        LiabilityView(
            id=2,
            scope="business",
            name="Loan",
            debt_type="business_loan",
            balance_gbp=2000,
            interest_rate_pct=10,
            minimum_payment_gbp=200,
            is_active=True,
        ),
    ]
    result = compute_safe_to_spend(
        totals=totals,
        personal=personal,
        business=business,
        liabilities=liabilities,
        personal_buffer_gbp=500,
        business_buffer_gbp=1000,
    )
    assert "breakdown" in result["personal"]
    assert "formula" in result["personal"]["breakdown"]
    assert result["personal"]["safe_to_spend_gbp"] == 1550.0  # 3000 - 900 - 50 - 500
    assert "disclaimer" in result["business"]["breakdown"]


def test_safe_to_spend_uses_resolved_open_banking_flow() -> None:
    totals = FinanceTotals(
        personal_cash_gbp=2000,
        business_cash_gbp=0,
        available_cash_gbp=2000,
        personal_overdraft_gbp=0,
        business_overdraft_gbp=0,
        available_credit_gbp=0,
        credit_limit_gbp=0,
        pension_gbp=0,
        property_gbp=0,
        other_assets_gbp=0,
        debtors_gbp=0,
        total_assets_gbp=2000,
        personal_debt_gbp=0,
        business_debt_gbp=0,
        credit_card_gbp=0,
        loan_gbp=0,
        mortgage_gbp=0,
        directors_loan_gbp=0,
        creditors_gbp=0,
        vat_reserve_gbp=0,
        corp_tax_reserve_gbp=0,
        total_liabilities_gbp=0,
        net_worth_gbp=2000,
        monthly_income_gbp=0,
        monthly_spending_gbp=0,
        monthly_surplus_gbp=0,
        cash_after_bills_gbp=0,
        vat_reserve_warning=False,
        corp_tax_reserve_warning=False,
        debt_reduction_gbp=0,
    )
    result = compute_safe_to_spend(
        totals=totals,
        personal=None,
        business=None,
        liabilities=[],
        personal_buffer_gbp=500,
        business_buffer_gbp=1000,
        flow_source="open_banking",
        resolved_income_gbp=3000,
        resolved_spending_gbp=1200,
        resolved_bills_gbp=900,
    )
    assert result["personal"]["flow_source"] == "open_banking"
    assert result["personal"]["safe_to_spend_gbp"] == 1600.0  # 3000 - 900 - 0 - 500
    assert "open banking" in result["personal"]["flow_note"].lower()


def test_safe_to_spend_budget_is_plan_not_cash() -> None:
    totals = FinanceTotals(
        personal_cash_gbp=2000,
        business_cash_gbp=0,
        available_cash_gbp=2000,
        personal_overdraft_gbp=0,
        business_overdraft_gbp=0,
        available_credit_gbp=0,
        credit_limit_gbp=0,
        pension_gbp=0,
        property_gbp=0,
        other_assets_gbp=0,
        debtors_gbp=0,
        total_assets_gbp=2000,
        personal_debt_gbp=0,
        business_debt_gbp=0,
        credit_card_gbp=0,
        loan_gbp=0,
        mortgage_gbp=0,
        directors_loan_gbp=0,
        creditors_gbp=0,
        vat_reserve_gbp=0,
        corp_tax_reserve_gbp=0,
        total_liabilities_gbp=0,
        net_worth_gbp=2000,
        monthly_income_gbp=0,
        monthly_spending_gbp=0,
        monthly_surplus_gbp=0,
        cash_after_bills_gbp=0,
        vat_reserve_warning=False,
        corp_tax_reserve_warning=False,
        debt_reduction_gbp=0,
    )
    result = compute_safe_to_spend(
        totals=totals,
        personal=None,
        business=None,
        liabilities=[],
        flow_source="budget",
        resolved_income_gbp=4000,
        resolved_spending_gbp=2500,
    )
    assert result["personal"]["safe_to_spend_gbp"] == 0.0
    assert result["personal"]["status"] == "BUDGET_PLAN_ONLY"
    assert result["personal"]["breakdown"]["budget_plan_income_gbp"] == 4000.0
    assert "budget plan" in result["personal"]["flow_note"].lower()
    assert "not live" in result["personal"]["flow_note"].lower()
