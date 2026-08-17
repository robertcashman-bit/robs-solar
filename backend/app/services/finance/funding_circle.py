"""Detect Funding Circle loans and repayments from Open Banking.

Funding Circle has no borrower balance API and the loan is not in QuickFile.
The automatic path is the business bank feed: loan drawdowns (credits) and
monthly repayments (debits) labelled Funding Circle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MARKERS = (
    "funding circle",
    "fundingcircle",
    "fndng circle",
    "fc loan",
    "funding-circle",
)


def is_funding_circle_text(value: str | None) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in _MARKERS)


def _description(transaction: dict[str, Any]) -> str:
    return " ".join(
        str(transaction.get(key) or "")
        for key in ("description", "merchant_name", "meta", "transaction_category")
    )


def _amount(transaction: dict[str, Any]) -> float:
    try:
        return float(transaction.get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def transaction_date(transaction: dict[str, Any]) -> str:
    raw = str(transaction.get("timestamp") or transaction.get("date") or "")
    return raw[:10]


def repayment_gbp(transaction: dict[str, Any]) -> float:
    """Return an outbound Funding Circle repayment amount, else 0."""
    if not is_funding_circle_text(_description(transaction)):
        return 0.0
    txn_type = str(transaction.get("transaction_type") or "").upper()
    if txn_type == "CREDIT":
        return 0.0
    amount = _amount(transaction)
    if amount == 0:
        return 0.0
    if txn_type == "DEBIT" or amount < 0:
        return round(abs(amount), 2)
    return 0.0


def drawdown_gbp(transaction: dict[str, Any]) -> float:
    """Return an inbound Funding Circle loan credit, else 0."""
    if not is_funding_circle_text(_description(transaction)):
        return 0.0
    txn_type = str(transaction.get("transaction_type") or "").upper()
    amount = _amount(transaction)
    if txn_type == "DEBIT" or amount < 0:
        return 0.0
    if txn_type == "CREDIT" or amount > 0:
        return round(abs(amount), 2)
    return 0.0


@dataclass(frozen=True)
class FundingCircleActivity:
    drawdown_gbp: float
    repayment_gbp: float
    latest_date: str
    latest_repayment_gbp: float
    count: int


def summarise_activity(
    transactions: list[dict[str, Any]],
    *,
    after_date: str = "",
) -> FundingCircleActivity:
    drawdown = 0.0
    repayment = 0.0
    latest = after_date
    latest_repayment = 0.0
    count = 0
    for item in transactions:
        day = transaction_date(item)
        if after_date and day and day <= after_date:
            continue
        credit = drawdown_gbp(item)
        debit = repayment_gbp(item)
        if credit == 0 and debit == 0:
            continue
        count += 1
        drawdown += credit
        repayment += debit
        if debit and (not latest or day >= latest):
            latest_repayment = debit
        if day > latest:
            latest = day
    return FundingCircleActivity(
        drawdown_gbp=round(drawdown, 2),
        repayment_gbp=round(repayment, 2),
        latest_date=latest,
        latest_repayment_gbp=round(latest_repayment, 2),
        count=count,
    )


def next_outstanding(
    current: float | None,
    activity: FundingCircleActivity,
    *,
    first_sync: bool,
) -> tuple[float | None, str]:
    """Return (outstanding, source). None means the current balance is unknown."""
    if activity.drawdown_gbp > 0:
        if first_sync:
            return max(0.0, activity.drawdown_gbp - activity.repayment_gbp), "open_banking"
        base = current or 0.0
        return max(0.0, base + activity.drawdown_gbp - activity.repayment_gbp), "open_banking"
    if current is None:
        return None, "needs_outstanding"
    if first_sync:
        return current, "seeded"
    return max(0.0, current - activity.repayment_gbp), "open_banking"
