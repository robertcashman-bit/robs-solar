"""Funding Circle detection and outstanding reconstruction."""

from app.integrations.truelayer_provider import infer_account_scope
from app.schemas.finance import FinanceScope
from app.services.finance.funding_circle import (
    drawdown_gbp,
    is_funding_circle_text,
    next_outstanding,
    repayment_gbp,
    summarise_activity,
)


def test_detects_funding_circle_labels() -> None:
    assert is_funding_circle_text("FUNDING CIRCLE LOAN")
    assert is_funding_circle_text("FundingCircle repayment")
    assert is_funding_circle_text("Fndng Circle")
    assert is_funding_circle_text("FC loan")
    assert is_funding_circle_text("funding-circle")
    assert not is_funding_circle_text("Tesco")
    assert not is_funding_circle_text("")


def test_drawdown_and_repayment_signs() -> None:
    credit = {
        "description": "Funding Circle",
        "amount": 12000,
        "transaction_type": "CREDIT",
        "timestamp": "2026-01-10",
    }
    debit = {
        "description": "Funding Circle",
        "amount": -450.25,
        "transaction_type": "DEBIT",
        "timestamp": "2026-02-10",
    }
    other = {"description": "Salary", "amount": 3000, "transaction_type": "CREDIT"}
    assert drawdown_gbp(credit) == 12000
    assert repayment_gbp(credit) == 0
    assert repayment_gbp(debit) == 450.25
    assert drawdown_gbp(debit) == 0
    assert drawdown_gbp(other) == 0
    assert repayment_gbp(other) == 0


def test_summarise_skips_transactions_on_or_before_cursor() -> None:
    activity = summarise_activity(
        [
            {
                "description": "Funding Circle",
                "amount": 10000,
                "transaction_type": "CREDIT",
                "timestamp": "2026-01-15",
            },
            {
                "description": "Funding Circle",
                "amount": -400,
                "transaction_type": "DEBIT",
                "timestamp": "2026-02-15",
            },
            {
                "description": "Funding Circle",
                "amount": -400,
                "transaction_type": "DEBIT",
                "timestamp": "2026-03-15",
            },
        ],
        after_date="2026-02-15",
    )
    assert activity.drawdown_gbp == 0
    assert activity.repayment_gbp == 400
    assert activity.count == 1
    assert activity.latest_date == "2026-03-15"


def test_next_outstanding_reconstructs_from_drawdown_on_first_sync() -> None:
    activity = summarise_activity(
        [
            {
                "description": "Funding Circle",
                "amount": 10000,
                "transaction_type": "CREDIT",
                "timestamp": "2026-01-15",
            },
            {
                "description": "Funding Circle",
                "amount": -450,
                "transaction_type": "DEBIT",
                "timestamp": "2026-02-15",
            },
        ]
    )
    outstanding, source = next_outstanding(None, activity, first_sync=True)
    assert outstanding == 9550
    assert source == "open_banking"


def test_next_outstanding_does_not_invent_balance_from_repayments_only() -> None:
    activity = summarise_activity(
        [
            {
                "description": "Funding Circle",
                "amount": -450,
                "transaction_type": "DEBIT",
                "timestamp": "2026-02-15",
            }
        ]
    )
    outstanding, source = next_outstanding(None, activity, first_sync=True)
    assert outstanding is None
    assert source == "needs_outstanding"


def test_next_outstanding_keeps_seed_on_first_sync_without_drawdown() -> None:
    activity = summarise_activity(
        [
            {
                "description": "Funding Circle",
                "amount": -450,
                "transaction_type": "DEBIT",
                "timestamp": "2026-02-15",
            }
        ]
    )
    outstanding, source = next_outstanding(8000, activity, first_sync=True)
    assert outstanding == 8000
    assert source == "seeded"


def test_next_outstanding_subtracts_new_repayments_later() -> None:
    activity = summarise_activity(
        [
            {
                "description": "Funding Circle",
                "amount": -450,
                "transaction_type": "DEBIT",
                "timestamp": "2026-04-15",
            }
        ]
    )
    outstanding, source = next_outstanding(8000, activity, first_sync=False)
    assert outstanding == 7550
    assert source == "open_banking"


def test_infer_business_scope_from_account_name() -> None:
    assert infer_account_scope("Business Current Account") == FinanceScope.BUSINESS
    assert infer_account_scope("Cashman Ltd") == FinanceScope.BUSINESS
    assert infer_account_scope("Everyday Current") == FinanceScope.PERSONAL
