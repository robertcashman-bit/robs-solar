"""Unit tests for debt priority and scenarios."""

from datetime import datetime, timezone

from app.schemas.finance import DebtType, FinanceLiability, FinanceScope
from app.services.finance.debt_strategy_service import (
    analyse_debts,
    months_to_payoff,
    recommend_debt_strategy,
    scenario_for_extra,
    total_interest_paid,
)


def _debt(
    debt_id: int,
    name: str,
    balance: float,
    apr: float,
    minimum: float,
    scope: FinanceScope = FinanceScope.PERSONAL,
    debt_type: DebtType = DebtType.CREDIT_CARD,
    interest_rate_known: bool = True,
) -> FinanceLiability:
    now = datetime.now(timezone.utc)
    return FinanceLiability(
        id=debt_id,
        scope=scope,
        name=name,
        debt_type=debt_type,
        balance_gbp=balance,
        interest_rate_pct=apr,
        minimum_payment_gbp=minimum,
        overpayment_gbp=0,
        interest_rate_known=interest_rate_known,
        created_at=now,
        updated_at=now,
    )


def test_months_to_payoff_zero_apr() -> None:
    assert months_to_payoff(1200, 0, 100) == 12


def test_months_to_payoff_insufficient_payment() -> None:
    assert months_to_payoff(1000, 24, 5) is None


def test_highest_apr_is_priority() -> None:
    analysis = analyse_debts(
        [
            _debt(1, "Cheap loan", 8000, 4.5, 150, debt_type=DebtType.LOAN),
            _debt(2, "MBNA", 1200, 24.9, 30),
        ]
    )
    assert analysis[0].name == "MBNA"
    assert analysis[0].priority_label == "Highest cost"
    assert analysis[0].monthly_interest_gbp is not None
    cheap = next(item for item in analysis if item.name == "Cheap loan")
    assert cheap.priority_label == "Low"


def test_priority_uses_apr_bands_not_monthly_interest_floor() -> None:
    """Large low-APR balances must not all collapse to Highest cost."""
    analysis = analyse_debts(
        [
            _debt(
                1,
                "House mortgage",
                82210.5,
                0.0,
                500,
                debt_type=DebtType.MORTGAGE,
                interest_rate_known=False,
            ),
            _debt(2, "Personal loan", 10000, 8.0, 200, debt_type=DebtType.LOAN),
            _debt(
                3,
                "Capital on Tap",
                10749,
                36.0,
                0,
                scope=FinanceScope.BUSINESS,
                debt_type=DebtType.LOAN,
            ),
            _debt(4, "Card", 2000, 19.9, 50),
        ]
    )
    by_name = {item.name: item.priority_label for item in analysis}
    assert by_name["Capital on Tap"] == "Highest cost"
    assert by_name["Card"] == "High"
    assert by_name["Personal loan"] == "Medium"
    assert by_name["House mortgage"] == "APR unknown"
    labels = set(by_name.values())
    assert len(labels) >= 3


def test_scenario_saves_interest_with_overpayment() -> None:
    debts = [_debt(1, "Card", 2000, 24, 80)]
    current = scenario_for_extra(debts, 0)
    extra = scenario_for_extra(debts, 100)
    assert current.incomplete is False
    assert extra.incomplete is False
    assert extra.months_with_extra is not None
    assert current.months_current is not None
    assert extra.months_with_extra < current.months_current
    assert extra.interest_saved_gbp is not None
    assert extra.interest_saved_gbp > 0


def test_scenario_zero_min_with_apr_models_interest_only() -> None:
    result = scenario_for_extra([_debt(1, "Capital on Tap", 10749, 36, 0)], 100)
    assert result.incomplete is False
    assert result.months_with_extra is not None
    assert result.payoff_date is not None
    assert "interest-only" in result.reason.lower()
    assert "Payment or APR is missing" not in result.reason


def test_scenario_zero_min_without_extra_asks_for_amount() -> None:
    result = scenario_for_extra([_debt(1, "Capital on Tap", 10749, 36, 0)], 0)
    assert result.incomplete is True
    assert "£0.00" in result.reason
    assert "APR is missing" not in result.reason


def test_recommend_strategy_uses_pound_sign_not_gbp_word() -> None:
    result = recommend_debt_strategy(
        [_debt(1, "Capital on Tap", 10749, 36, 0, debt_type=DebtType.BUSINESS_LOAN)]
    )
    assert "GBP" not in result.message
    assert "£" in result.message


def test_scenario_incomplete_when_all_apr_unknown() -> None:
    result = scenario_for_extra(
        [
            _debt(1, "Small unknown", 400, 0, 20, interest_rate_known=False),
            _debt(2, "Large unknown", 5000, 0, 50, interest_rate_known=False),
        ],
        100,
    )
    assert result.incomplete is True
    assert "APR is missing" in result.reason
    assert "Large unknown" in result.reason


def test_scenario_prefers_known_apr_over_larger_unknown_balance() -> None:
    result = scenario_for_extra(
        [
            _debt(1, "High APR", 200, 24, 20),
            _debt(2, "Large unknown", 5000, 0, 50, interest_rate_known=False),
        ],
        100,
    )
    assert result.incomplete is False
    assert "High APR" in result.reason
    assert "highest APR" in result.reason


def test_recommend_strategy_includes_analysis() -> None:
    result = recommend_debt_strategy([_debt(1, "Card", 900, 22, 40)])
    assert result.strategy == "avalanche"
    assert result.analysis
    assert result.scenarios
    assert total_interest_paid(900, 22, 40) is not None


def test_no_debts_recommendation() -> None:
    result = recommend_debt_strategy([])
    assert result.strategy == "none"
    assert "no active debts" in result.headline.lower()


def test_only_directors_loan_counts_as_no_repayable_debt() -> None:
    result = recommend_debt_strategy(
        [_debt(1, "DLA", 20000, 0, 0, debt_type=DebtType.DIRECTORS_LOAN)]
    )
    assert result.strategy == "none"


def test_directors_loan_is_not_a_repayable_debt() -> None:
    result = recommend_debt_strategy(
        [
            _debt(1, "DLA", 20000, 0, 0, debt_type=DebtType.DIRECTORS_LOAN),
            _debt(2, "Card", 900, 22, 40),
        ]
    )
    assert result.strategy == "avalanche"
    assert "Card" in result.message
    assert all(item.name != "DLA" for item in result.analysis)


def test_avalanche_picks_high_interest() -> None:
    debts = [
        _debt(1, "Low", 500, 5, 50, debt_type=DebtType.LOAN),
        _debt(2, "High", 3000, 24, 50),
    ]
    result = recommend_debt_strategy(debts)
    assert result.strategy == "avalanche"
    assert "High" in result.message


def test_personal_and_business_strategies_are_separate() -> None:
    from app.services.finance.debt_strategy_service import recommend_dual_debt_strategies

    debts = [
        _debt(1, "MBNA", 1000, 0, 30, interest_rate_known=False),
        _debt(2, "Virgin", 500, 19.9, 25),
        _debt(
            3,
            "Capital on Tap",
            9500,
            36,
            0,
            scope=FinanceScope.BUSINESS,
            debt_type=DebtType.CREDIT_CARD,
        ),
        _debt(
            4,
            "House mortgage",
            82210.5,
            0,
            500,
            debt_type=DebtType.MORTGAGE,
            interest_rate_known=False,
        ),
    ]
    dual = recommend_dual_debt_strategies(debts)
    assert dual.personal.focus_debt_name == "Virgin"
    assert dual.personal.incomplete is True
    reason = dual.personal.incomplete_reason or ""
    assert "MBNA" in reason or "mortgage" in reason.lower()
    assert dual.business.focus_debt_name == "Capital on Tap"
    assert dual.business.incomplete is False
    assert all(row.scope == "personal" for row in dual.personal.payoff_order)
    assert all(row.scope == "business" for row in dual.business.payoff_order)
    mortgage = next(row for row in dual.personal.debts if row["debt_type"] == "mortgage")
    assert mortgage["is_mortgage"] is True
    assert "half-share" in mortgage["order_reason"]


def test_scoped_scenarios_do_not_cross_stacks() -> None:
    debts = [
        _debt(1, "Personal card", 1000, 22, 40),
        _debt(
            2,
            "Capital on Tap",
            9500,
            36,
            0,
            scope=FinanceScope.BUSINESS,
            debt_type=DebtType.CREDIT_CARD,
        ),
    ]
    personal = scenario_for_extra(debts, 100, scope="personal")
    business = scenario_for_extra(debts, 100, scope="business")
    assert "Personal card" in personal.reason
    assert "Capital on Tap" in business.reason
