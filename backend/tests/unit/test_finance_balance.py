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
