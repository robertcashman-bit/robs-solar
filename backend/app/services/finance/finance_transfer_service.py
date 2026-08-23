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
            # Description-only mark: clear own-account hints only. Payment rails
            # (FPS/BACS/Faster Payment) alone never mark a row as a transfer —
            # that requires an opposite-leg pair below.
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
                # Salary-looking credits should not be paired away as transfers
                # unless the counterpart also looks like an internal move.
                left_salary = finance_categoriser_service.looks_like_salary(left.description)
                right_salary = finance_categoriser_service.looks_like_salary(right.description)
                if left_salary or right_salary:
                    pair_text = f"{left.description} {right.description}"
                    if not finance_categoriser_service.looks_like_transfer(pair_text):
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

    async def unmark_false_transfers(
        self,
        db: AsyncSession,
        *,
        persist: bool = True,
        redetect: bool = True,
    ) -> dict[str, Any]:
        """Clear transfer flags that came from payment-rail false positives.

        Keeps rows with an opposite-leg ``transfer_group_id`` and rows whose
        description still has a clear own-account hint. Re-categorises cleared
        rows and optionally re-runs pair detection.
        """
        rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.is_deleted.is_(False),
                        FinanceTransactionRow.is_transfer.is_(True),
                    )
                )
            ).all()
        )
        cleared = 0
        now = datetime.now(timezone.utc)
        for row in rows:
            if row.transfer_group_id:
                continue
            if finance_categoriser_service.looks_like_transfer(row.description):
                continue
            # Unpaired + no own-account hint → legacy false positive (FPS/BACS
            # salary credits, rails-only marks, etc.).
            row.is_transfer = False
            row.txn_type = "income" if row.amount_pence > 0 else "expense"
            row.updated_at = now
            if (row.category or "").strip() == "Transfers":
                guessed = await finance_categoriser_service.categorise(
                    db, row.description, scope=row.scope
                )
                row.category = guessed.get("category") or ""
                row.category_confidence = guessed.get("confidence") or ""
            if row.subcategory == "needs_review":
                row.subcategory = ""
            cleared += 1

        if persist:
            await db.commit()
        else:
            await db.flush()

        redetect_result: dict[str, Any] = {}
        if redetect:
            redetect_result = await self.detect_and_mark(
                db, lookback_days=400, persist=persist
            )
        return {
            "cleared": cleared,
            "examined": len(rows),
            "redetect": redetect_result,
            "message": (
                f"Cleared {cleared} false transfer flag(s). "
                "Opposite-leg pairs and own-account wording were kept."
            ),
        }

    async def resolve_review(
        self,
        db: AsyncSession,
        *,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Resolve transfer-review rows that are no longer transfers.

        Cross-scope pairs keep ``needs_review`` until manually categorised.
        False-positive transfer marks are cleared via ``unmark_false_transfers``.
        """
        unmarked = await self.unmark_false_transfers(db, persist=persist, redetect=True)
        remaining = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.is_deleted.is_(False),
                        FinanceTransactionRow.subcategory == "needs_review",
                    )
                )
            ).all()
        )
        return {
            **unmarked,
            "remaining_review": len(remaining),
            "message": (
                f"{unmarked.get('message', '')} "
                f"{len(remaining)} cross-scope pair(s) still need review."
            ).strip(),
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
