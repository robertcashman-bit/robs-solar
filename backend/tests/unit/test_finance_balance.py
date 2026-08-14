"""Unit tests for finance balance / net worth breakdown."""

from datetime import datetime, timezone

from app.schemas.finance import (
    DebtType,
    FinanceAccount,
    FinanceAccountSource,
    FinanceAccountType,
    FinanceLiability,
    FinanceScope,
)
from app.services.finance.finance_balance_service import build_balance_breakdown

_NOW = datetime.now(timezone.utc)


def _account(**kwargs) -> FinanceAccount:
    defaults = dict(
        id=1,
        scope=FinanceScope.PERSONAL,
        account_type=FinanceAccountType.CURRENT,
        name="Test",
        provider="",
        balance_gbp=0.0,
        notes="",
        source=FinanceAccountSource.MANUAL,
        is_active=True,
        is_historic=True,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(kwargs)
    return FinanceAccount(**defaults)


def _liability(**kwargs) -> FinanceLiability:
    defaults = dict(
        id=1,
        scope=FinanceScope.PERSONAL,
        name="Debt",
        debt_type=DebtType.CREDIT_CARD,
        balance_gbp=0.0,
        interest_rate_pct=0.0,
        minimum_payment_gbp=0.0,
        notes="",
        is_active=True,
        is_historic=True,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(kwargs)
    return FinanceLiability(**defaults)


def test_net_worth_without_property_is_deeply_negative() -> None:
    """Mortgage without property value produces a misleading negative net worth."""
    accounts = [
        _account(account_type=FinanceAccountType.CURRENT, balance_gbp=2500),
        _account(account_type=FinanceAccountType.PENSION, balance_gbp=50000),
    ]
    liabilities = [
        _liability(name="Mortgage", debt_type=DebtType.MORTGAGE, balance_gbp=150_000),
    ]
    b = build_balance_breakdown(accounts, liabilities)
    assert b.property_value_gbp == 0.0
    assert b.mortgage_balance_gbp == 150_000.0
    assert b.personal_long_term_debt_gbp == 150_000.0
    assert b.net_worth_estimate_gbp == 52_500.0 - 150_000.0


def test_directors_loan_credit_balance_counts_as_debt() -> None:
    """QuickFile stores director's loan as negative credit — debt totals use magnitude."""
    accounts = [
        _account(
            scope=FinanceScope.BUSINESS, balance_gbp=10_000, account_type=FinanceAccountType.CURRENT
        ),
        _account(
            scope=FinanceScope.BUSINESS,
            account_type=FinanceAccountType.DIRECTORS_LOAN,
            name="Directors Loan",
            balance_gbp=-16_950.52,
        ),
    ]
    b = build_balance_breakdown(accounts, [])
    assert b.directors_loan_gbp == 16_950.52
    assert b.business_long_term_debt_gbp == 16_950.52
    assert b.total_debt_gbp == 16_950.52
    assert b.net_worth_estimate_gbp == 10_000.0 - 16_950.52


def test_net_worth_with_property_reflects_home_equity() -> None:
    accounts = [
        _account(account_type=FinanceAccountType.CURRENT, balance_gbp=2500),
        _account(account_type=FinanceAccountType.PENSION, balance_gbp=50_000),
        _account(
            account_type=FinanceAccountType.PROPERTY,
            name="Greenacre",
            balance_gbp=425_000,
        ),
    ]
    liabilities = [
        _liability(name="Mortgage", debt_type=DebtType.MORTGAGE, balance_gbp=150_000),
        _liability(name="Virgin", debt_type=DebtType.CREDIT_CARD, balance_gbp=450),
    ]
    b = build_balance_breakdown(accounts, liabilities)
    assert b.home_equity_gbp == 275_000.0
    assert b.personal_short_term_debt_gbp == 450.0
    assert b.personal_long_term_debt_gbp == 150_000.0
    # 2500 + 50000 + 425000 - 150450
    assert b.net_worth_estimate_gbp == 327_050.0


def test_personal_overdraft_counts_as_short_term_debt() -> None:
    accounts = [
        _account(account_type=FinanceAccountType.CURRENT, balance_gbp=-500.0),
    ]
    b = build_balance_breakdown(accounts, [])
    assert b.liquid_assets_gbp == 0.0
    assert b.personal_short_term_debt_gbp == 500.0
    assert b.personal_total_debt_gbp == 500.0
    assert b.net_worth_estimate_gbp == -500.0


def test_mixed_current_balances_do_not_net_overdraft() -> None:
    accounts = [
        _account(id=1, name="Current", balance_gbp=-2657.45),
        _account(id=2, name="Saver", account_type=FinanceAccountType.SAVINGS, balance_gbp=13.12),
        _account(id=3, name="Other", balance_gbp=1725.06),
    ]
    b = build_balance_breakdown(accounts, [])
    assert b.liquid_assets_gbp == round(13.12 + 1725.06, 2)
    assert b.personal_short_term_debt_gbp == 2657.45
    assert b.net_worth_estimate_gbp == round(13.12 + 1725.06 - 2657.45, 2)


def test_mock_aspsp_excluded_from_liquid_assets() -> None:
    accounts = [
        _account(id=1, balance_gbp=100.0),
        _account(
            id=19,
            name="Mock ASPSP",
            provider="Mock ASPSP",
            source=FinanceAccountSource.OPEN_BANKING,
            balance_gbp=13066.2,
        ),
    ]
    b = build_balance_breakdown(accounts, [])
    assert b.liquid_assets_gbp == 100.0


def test_business_liabilities_included_in_debt_totals() -> None:
    accounts = [
        _account(
            id=1,
            scope=FinanceScope.BUSINESS,
            account_type=FinanceAccountType.CURRENT,
            balance_gbp=5_000.0,
        ),
    ]
    liabilities = [
        _liability(
            id=1,
            scope=FinanceScope.BUSINESS,
            name="Business loan",
            debt_type=DebtType.BUSINESS_LOAN,
            balance_gbp=8_000.0,
        ),
        _liability(
            id=2,
            scope=FinanceScope.BUSINESS,
            name="Biz card",
            debt_type=DebtType.CREDIT_CARD,
            balance_gbp=1_200.0,
        ),
    ]
    b = build_balance_breakdown(accounts, liabilities)
    assert b.business_short_term_debt_gbp == 1_200.0
    assert b.business_long_term_debt_gbp == 8_000.0
    assert b.business_total_debt_gbp == 9_200.0
    assert b.total_debt_gbp == 9_200.0


def test_explicit_zero_debtors_does_not_fall_back_to_accounts() -> None:
    accounts = [
        _account(
            scope=FinanceScope.BUSINESS,
            account_type=FinanceAccountType.DEBTORS,
            balance_gbp=1_200.0,
        ),
    ]
    b = build_balance_breakdown(accounts, [], debtors_gbp=0.0)
    assert b.debtors_gbp == 0.0
    assert b.long_term_assets_gbp == 0.0
