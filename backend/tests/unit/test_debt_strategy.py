"""Unit tests for debt strategy service."""

from datetime import datetime, timezone

from app.schemas.finance import DebtType, FinanceLiability, FinanceScope
from app.services.finance.debt_strategy_service import recommend_debt_strategy


def _liability(**kwargs) -> FinanceLiability:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=1,
        scope=FinanceScope.PERSONAL,
        name="Card",
        debt_type=DebtType.CREDIT_CARD,
        balance_gbp=2000,
        interest_rate_pct=22,
        minimum_payment_gbp=50,
        overpayment_gbp=0,
        payment_day=1,
        account_id=None,
        notes="",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return FinanceLiability(**defaults)


def test_no_debts_recommendation() -> None:
    result = recommend_debt_strategy([])
    assert result.strategy == "none"
    assert result.headline == "No active debts"


def test_avalanche_picks_high_interest() -> None:
    debts = [
        _liability(id=1, name="Low", balance_gbp=500, interest_rate_pct=5),
        _liability(id=2, name="High", balance_gbp=3000, interest_rate_pct=24),
    ]
    result = recommend_debt_strategy(debts)
    assert result.strategy == "avalanche"
    assert "High" in result.message
