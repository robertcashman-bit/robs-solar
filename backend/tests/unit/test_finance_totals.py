"""Unit tests for shared finance totals."""

from datetime import datetime, timezone

from app.schemas.finance import (
    DebtType,
    FinanceAccount,
    FinanceAccountSource,
    FinanceAccountType,
    FinanceLiability,
    FinanceScope,
)
from app.services.finance.finance_totals import (
    CREDIT_CARD_LIABILITY_TYPES,
    category_total,
    net_worth_assets_gbp,
    net_worth_debt_gbp,
)
from app.services.finance.snapshot_dates import normalize_snapshot_date, snapshot_in_month


def _account(**kwargs) -> FinanceAccount:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=1,
        scope=FinanceScope.PERSONAL,
        account_type=FinanceAccountType.CURRENT,
        name="Account",
        provider="",
        balance_gbp=0.0,
        source=FinanceAccountSource.MANUAL,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return FinanceAccount(**defaults)


def _liability(**kwargs) -> FinanceLiability:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=1,
        scope=FinanceScope.PERSONAL,
        name="Debt",
        debt_type=DebtType.CREDIT_CARD,
        balance_gbp=0.0,
        interest_rate_pct=0.0,
        minimum_payment_gbp=0.0,
        overpayment_gbp=0.0,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return FinanceLiability(**defaults)


def test_net_worth_debt_counts_liability_once() -> None:
    liabilities = [_liability(id=1, balance_gbp=400)]
    assert net_worth_debt_gbp([], liabilities) == 400
    assert category_total(
        [], liabilities, FinanceAccountType.CREDIT_CARD, CREDIT_CARD_LIABILITY_TYPES
    ) == 400


def test_net_worth_debt_includes_unlinked_account_and_liability() -> None:
    accounts = [_account(id=2, account_type=FinanceAccountType.CREDIT_CARD, balance_gbp=250)]
    liabilities = [_liability(id=3, balance_gbp=400, account_id=None)]
    assert net_worth_debt_gbp(accounts, liabilities) == 650


def test_net_worth_debt_dedupes_linked_liability() -> None:
    accounts = [_account(id=8, account_type=FinanceAccountType.CREDIT_CARD, balance_gbp=300)]
    liabilities = [_liability(id=9, balance_gbp=300, account_id=8)]
    assert net_worth_debt_gbp(accounts, liabilities) == 300
    assert category_total(
        accounts, liabilities, FinanceAccountType.CREDIT_CARD, CREDIT_CARD_LIABILITY_TYPES
    ) == 300


def test_net_worth_assets_formula() -> None:
    assert net_worth_assets_gbp(2000, 5000, 10000, 750) == 17750


def test_normalize_month_only_snapshot_date() -> None:
    assert normalize_snapshot_date("2026-08") == "2026-08-01"
    assert normalize_snapshot_date("2026-08-15") == "2026-08-15"


def test_snapshot_in_month_accepts_month_or_day() -> None:
    assert snapshot_in_month("2026-08", "2026-08")
    assert snapshot_in_month("2026-08-01", "2026-08")
    assert not snapshot_in_month("2026-07-31", "2026-08")
