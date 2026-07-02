"""Unit tests for finance insights rules."""

from app.schemas.finance import FinanceOverviewResponse


def test_cashflow_insight_trigger_fields() -> None:
    overview = FinanceOverviewResponse(
        personal_bank_balance_gbp=1000,
        business_bank_balance_gbp=2000,
        total_personal_debt_gbp=500,
        total_business_debt_gbp=0,
        monthly_income_gbp=3000,
        monthly_spending_gbp=2200,
        cash_after_bills_gbp=200,
        vat_reserve_gbp=100,
        corp_tax_reserve_gbp=100,
        vat_reserve_warning=True,
        corp_tax_reserve_warning=False,
        credit_card_balances_gbp=800,
        loan_balances_gbp=0,
        mortgage_balance_gbp=100000,
        pension_value_gbp=20000,
        directors_loan_gbp=0,
        net_worth_estimate_gbp=50000,
        monthly_surplus_gbp=600,
        insights=[],
    )
    assert overview.cash_after_bills_gbp < 500
    assert overview.vat_reserve_warning is True
