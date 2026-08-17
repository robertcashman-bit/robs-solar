"""Detect likely internal transfers so they are not treated as spend/income."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceTransactionRow
from app.services.finance.finance_categoriser_service import finance_categoriser_service
from app.services.finance.finance_ledger_service import finance_ledger_service


def _parse(day: str) -> date | None:
    try:
        return date.fromisoformat(day[:10])
    except ValueError:
        return None


class FinanceTransferService:
    async def detect_and_mark(
        self,
        db: AsyncSession,
        *,
        lookback_days: int = 120,
        persist: bool = True,
    ) -> dict[str, Any]:
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=lookback_days)).isoformat()
        rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow)
                    .where(
                        FinanceTransactionRow.is_deleted.is_(False),
                        FinanceTransactionRow.posted_on >= cutoff,
                    )
                    .order_by(FinanceTransactionRow.posted_on.asc(), FinanceTransactionRow.id.asc())
                )
            ).all()
        )
        linked = 0
        flagged_review = 0
        used: set[int] = set()
        now = datetime.now(timezone.utc)

        for index, left in enumerate(rows):
            if left.id in used:
                continue
            left_day = _parse(left.posted_on)
            if left_day is None or left.amount_pence == 0:
                continue
            if finance_categoriser_service.looks_like_transfer(left.description):
                if not left.is_transfer:
                    left.is_transfer = True
                    left.txn_type = "transfer"
                    left.updated_at = now
                    if not (left.category or "").strip():
                        left.category = "Transfers"
                    linked += 1

            for right in rows[index + 1 :]:
                if right.id in used:
                    continue
                right_day = _parse(right.posted_on)
                if right_day is None:
                    continue
                if abs((right_day - left_day).days) > 1:
                    if right_day > left_day + timedelta(days=1):
                        break
                    continue
                if left.amount_pence + right.amount_pence != 0:
                    continue
                same_account = (
                    left.account_id is not None
                    and right.account_id is not None
                    and left.account_id == right.account_id
                )
                if same_account and not finance_categoriser_service.looks_like_transfer(
                    left.description + " " + right.description
                ):
                    continue

                left.is_transfer = True
                right.is_transfer = True
                left.txn_type = "transfer"
                right.txn_type = "transfer"
                left.updated_at = now
                right.updated_at = now
                if not (left.category or "").strip():
                    left.category = "Transfers"
                if not (right.category or "").strip():
                    right.category = "Transfers"
                if left.scope != right.scope:
                    left.subcategory = left.subcategory or "needs_review"
                    right.subcategory = right.subcategory or "needs_review"
                    flagged_review += 1
                if hasattr(left, "transfer_group_id"):
                    pair_tag = f"xfer:{min(left.id, right.id)}-{max(left.id, right.id)}"
                    left.transfer_group_id = pair_tag
                    right.transfer_group_id = pair_tag
                used.add(left.id)
                used.add(right.id)
                linked += 1
                break

        if persist:
            await db.commit()
        else:
            await db.flush()
        return {
            "examined": len(rows),
            "marked_or_linked": linked,
            "needs_review": flagged_review,
            "message": (
                "Transfers are excluded from expenditure totals but kept for cashflow."
            ),
        }

    async def list_needs_review(self, db: AsyncSession, limit: int = 100) -> list[dict[str, Any]]:
        rows = (
            await db.scalars(
                select(FinanceTransactionRow)
                .where(
                    FinanceTransactionRow.is_deleted.is_(False),
                    FinanceTransactionRow.subcategory == "needs_review",
                )
                .order_by(FinanceTransactionRow.posted_on.desc())
                .limit(limit)
            )
        ).all()
        return [finance_ledger_service.to_public(row) for row in rows]


finance_transfer_service = FinanceTransferService()
