"""Lunch Flow scope, business connections, and credit-card balance rules."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow
from app.schemas.finance import FinanceAccountSource, FinanceAccountType, FinanceScope
from app.services.finance.funding_circle import infer_account_scope
from app.services.finance.lunchflow_account_ids import (
    LUNCHFLOW_SOURCES,
    normalize_lunchflow_external_id,
)

_LAST_FOUR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")


def parse_business_connection_ids(raw: str | list[str] | None) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if isinstance(raw, list):
        return frozenset(str(item).strip() for item in raw if str(item).strip())
    return frozenset(part.strip() for part in str(raw).split(",") if part.strip())


def parse_quickfile_shadow_map(raw: str | dict[str, int] | None) -> dict[str, int]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {
            normalize_lunchflow_external_id(str(key)): int(value)
            for key, value in raw.items()
            if normalize_lunchflow_external_id(str(key)) and value
        }
    mapping: dict[str, int] = {}
    for part in str(raw).split(","):
        chunk = part.strip()
        if not chunk or ":" not in chunk:
            continue
        left, right = chunk.split(":", 1)
        lf_id = normalize_lunchflow_external_id(left.strip())
        try:
            finance_id = int(right.strip())
        except ValueError:
            continue
        if lf_id and finance_id > 0:
            mapping[lf_id] = finance_id
    return mapping


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
        return round(fallback, 2)

    provider = current if current is not None else fallback
    if (
        available is not None
        and 0 <= available <= limit
        and provider > 0
        and provider <= limit
    ):
        return round(limit - available, 2)

    if current is not None:
        if current <= 0:
            return round(abs(current), 2)
        if current / limit >= 0.5:
            return round(current, 2)
        return round(limit - current, 2)

    if fallback <= 0:
        return round(abs(fallback), 2)

    if 0 < fallback < limit * 0.5:
        return round(limit - fallback, 2)
    return round(max(fallback, 0.0), 2)


def sync_balance_gbp(
    *,
    account_type: str,
    credit_limit_gbp: float | None,
    item: dict[str, Any],
) -> float:
    """Apply card owed rules using preserved account type and raw provider balance fields."""
    return credit_card_balance_gbp(
        account_type=FinanceAccountType(account_type),
        credit_limit_gbp=credit_limit_gbp,
        current=_optional_float(item.get("balance_current")),
        available=_optional_float(item.get("balance_available")),
        fallback=float(item.get("balance_gbp") or 0.0),
    )


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _digit_tokens(*values: str | None) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        text = (value or "").strip()
        if not text:
            continue
        tokens.update(_LAST_FOUR_RE.findall(text))
    return tokens


def quickfile_strong_match(lf_row: FinanceAccountRow, qf_row: FinanceAccountRow) -> bool:
    """True only when type matches and a 4-digit suffix aligns (e.g. card ending 5393)."""
    if lf_row.account_type != qf_row.account_type:
        return False
    lf_digits = _digit_tokens(lf_row.name, lf_row.external_id, lf_row.provider)
    qf_digits = _digit_tokens(qf_row.name, qf_row.external_id, qf_row.provider, qf_row.notes)
    shared = lf_digits & qf_digits
    return bool(shared)


async def _quickfile_target_row(
    db: AsyncSession, finance_account_id: int
) -> FinanceAccountRow | None:
    row = await db.get(FinanceAccountRow, finance_account_id)
    if row is None:
        return None
    if row.source != FinanceAccountSource.QUICKFILE.value:
        return None
    if row.scope != FinanceScope.BUSINESS.value:
        return None
    if not row.is_active:
        return None
    return row


async def mark_quickfile_shadow_if_needed(
    db: AsyncSession,
    row: FinanceAccountRow,
    *,
    quickfile_shadow_map: dict[str, int] | None = None,
) -> None:
    """Mark reference-only LF rows when explicitly mapped or strongly matched to QuickFile."""
    if row.scope != FinanceScope.BUSINESS.value:
        return
    if row.source not in LUNCHFLOW_SOURCES:
        return
    if row.exclude_from_totals and row.mirrors_account_id is not None:
        return

    shadow_map = quickfile_shadow_map or {}
    canonical = normalize_lunchflow_external_id(row.external_id or "")
    mapped_id = shadow_map.get(canonical) if canonical else None
    target: FinanceAccountRow | None = None
    if mapped_id is not None:
        target = await _quickfile_target_row(db, mapped_id)

    if target is None:
        qf_rows = list(
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
        for candidate in qf_rows:
            if quickfile_strong_match(row, candidate):
                target = candidate
                break

    if target is None:
        return
    row.exclude_from_totals = True
    row.mirrors_account_id = target.id
