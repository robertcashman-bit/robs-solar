"""Lunch Flow scope, business connections, and credit-card balance rules."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow
from app.schemas.finance import FinanceAccountSource, FinanceAccountType, FinanceScope
from app.services.finance.funding_circle import infer_account_scope
from app.services.finance.lunchflow_account_ids import LUNCHFLOW_SOURCES


def parse_business_connection_ids(raw: str | list[str] | None) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, list):
        return frozenset(str(item).strip() for item in raw if str(item).strip())
    return frozenset(part.strip() for part in str(raw).split(",") if part.strip())


def lunchflow_connection_id(record: dict[str, Any]) -> str:
    for key in (
        "connectionId",
        "connection_id",
        "connectionID",
        "bankConnectionId",
        "bank_connection_id",
        "linkId",
        "link_id",
    ):
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    nested = record.get("connection")
    if isinstance(nested, dict):
        for key in ("id", "connectionId", "connection_id"):
            value = nested.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return ""


def infer_lunchflow_scope(
    record: dict[str, Any],
    *,
    display_name: str,
    provider_name: str,
    business_connection_ids: frozenset[str] | None = None,
) -> FinanceScope:
    connection_ids = business_connection_ids or frozenset()
    connection = lunchflow_connection_id(record)
    if connection and connection in connection_ids:
        return FinanceScope.BUSINESS
    return infer_account_scope(display_name, provider_name)


def credit_card_balance_gbp(
    *,
    account_type: FinanceAccountType,
    credit_limit_gbp: float | None,
    current: float | None,
    available: float | None,
    fallback: float,
) -> float:
    """Return amount owed on the card (positive = debt). Never treat available credit as cash."""
    if account_type != FinanceAccountType.CREDIT_CARD:
        return round(fallback, 2)
    limit = credit_limit_gbp
    if limit is None or limit <= 0:
        return round(max(fallback, 0.0), 2)

    if available is not None and 0 <= available <= limit:
        return round(limit - available, 2)

    if current is not None:
        if current <= 0:
            return round(abs(current), 2)
        if current / limit >= 0.5:
            return round(current, 2)
        return round(limit - current, 2)

    if 0 < fallback < limit * 0.5:
        return round(limit - fallback, 2)
    return round(max(fallback, 0.0), 2)


async def mark_quickfile_shadow_if_needed(db: AsyncSession, row: FinanceAccountRow) -> None:
    """Business Lunch Flow rows that mirror QuickFile stay reference-only for totals."""
    if row.scope != FinanceScope.BUSINESS.value:
        return
    if row.source not in LUNCHFLOW_SOURCES:
        return
    if row.exclude_from_totals:
        return
    matches = list(
        (
            await db.scalars(
                select(FinanceAccountRow).where(
                    FinanceAccountRow.source == FinanceAccountSource.QUICKFILE.value,
                    FinanceAccountRow.scope == FinanceScope.BUSINESS.value,
                    FinanceAccountRow.account_type == row.account_type,
                    FinanceAccountRow.is_active.is_(True),
                )
            )
        ).all()
    )
    if not matches:
        return
    row.exclude_from_totals = True
    if row.mirrors_account_id is None:
        row.mirrors_account_id = matches[0].id
