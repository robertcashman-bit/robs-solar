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
        # Clear salary / cross-scope false positives before pairing again so
        # already-flagged August wages return as income on the next pass.
        cleared = await self._clear_false_transfer_marks(db, persist=False)

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
                if not self._should_pair_as_transfer(left, right):
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
            "cleared_false_transfers": cleared,
            "needs_review": flagged_review,
            "message": (
                "Transfers are excluded from expenditure totals but kept for cashflow."
            ),
        }

    def _should_pair_as_transfer(
        self,
        left: FinanceTransactionRow,
        right: FinanceTransactionRow,
    ) -> bool:
        """Decide whether equal-and-opposite legs are a real internal transfer."""
        pair_text = f"{left.description} {right.description}"
        left_salary = finance_categoriser_service.looks_like_salary(left.description)
        right_salary = finance_categoriser_service.looks_like_salary(right.description)
        if left_salary or right_salary:
            # Salary-looking credits stay income unless the pair is clearly
            # an own-account move (rare).
            if not finance_categoriser_service.looks_like_transfer(pair_text):
                return False

        cross_scope = left.scope != right.scope
        if cross_scope:
            # Business debit + personal credit of the same amount is usually
            # payroll or DLA — not "between my accounts" — unless wording says so.
            return finance_categoriser_service.looks_like_cross_scope_transfer(pair_text)

        same_account = (
            left.account_id is not None
            and right.account_id is not None
            and left.account_id == right.account_id
        )
        if same_account and not finance_categoriser_service.looks_like_transfer(pair_text):
            return False
        return True

    async def _clear_false_transfer_marks(
        self,
        db: AsyncSession,
        *,
        persist: bool,
    ) -> int:
        """Unmark salary and cross-scope false positives, including paired legs."""
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
        by_id = {row.id: row for row in rows}
        by_group: dict[str, list[FinanceTransactionRow]] = {}
        for row in rows:
            group = (row.transfer_group_id or "").strip()
            if group:
                by_group.setdefault(group, []).append(row)

        to_clear: set[int] = set()
        for row in rows:
            if row.id in to_clear:
                continue
            group = (row.transfer_group_id or "").strip()
            partners = list(by_group.get(group) or []) if group else []
            # Unpaired + no own-account hint → legacy FPS/BACS false positive.
            if not group or len(partners) < 2:
                if finance_categoriser_service.looks_like_transfer(row.description):
                    continue
                to_clear.add(row.id)
                continue

            # Paired: clear when the pair would not be made under current rules.
            if not self._paired_group_still_valid(partners):
                for partner in partners:
                    to_clear.add(partner.id)

        # Also catch orphan group ids where the partner is not transfer-marked.
        for row in rows:
            if row.id in to_clear:
                continue
            if finance_categoriser_service.looks_like_salary(row.description):
                if not finance_categoriser_service.looks_like_transfer(row.description):
                    to_clear.add(row.id)

        cleared = 0
        now = datetime.now(timezone.utc)
        for row_id in to_clear:
            row = by_id.get(row_id)
            if row is None:
                continue
            await self._unmark_row(db, row, now=now)
            cleared += 1

        if persist:
            await db.commit()
        else:
            await db.flush()
        return cleared

    def _paired_group_still_valid(self, partners: list[FinanceTransactionRow]) -> bool:
        if len(partners) < 2:
            return False
        # Validate each opposite-sign combination; if any valid pair remains, keep.
        for index, left in enumerate(partners):
            for right in partners[index + 1 :]:
                if left.amount_pence + right.amount_pence != 0:
                    continue
                left_day = _parse(left.posted_on)
                right_day = _parse(right.posted_on)
                if left_day is None or right_day is None:
                    continue
                if abs((right_day - left_day).days) > 1:
                    continue
                if self._should_pair_as_transfer(left, right):
                    return True
        return False

    async def _unmark_row(
        self,
        db: AsyncSession,
        row: FinanceTransactionRow,
        *,
        now: datetime,
    ) -> None:
        row.is_transfer = False
        row.txn_type = "income" if row.amount_pence > 0 else "expense"
        row.transfer_group_id = None
        row.updated_at = now
        if (row.category or "").strip() == "Transfers":
            guessed = await finance_categoriser_service.categorise(
                db, row.description, scope=row.scope
            )
            row.category = guessed.get("category") or ""
            row.category_confidence = guessed.get("confidence") or ""
        if row.subcategory == "needs_review":
            row.subcategory = ""

    async def unmark_false_transfers(
        self,
        db: AsyncSession,
        *,
        persist: bool = True,
        redetect: bool = True,
    ) -> dict[str, Any]:
        """Clear transfer flags that came from payment-rail or payroll false positives.

        Clears unpaired rails-only marks and cross-scope / salary pairs that are
        not clear own-account moves. Optionally re-runs pair detection.
        """
        rows_before = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.is_deleted.is_(False),
                        FinanceTransactionRow.is_transfer.is_(True),
                    )
                )
            ).all()
        )
        cleared = await self._clear_false_transfer_marks(db, persist=persist)

        redetect_result: dict[str, Any] = {}
        if redetect:
            redetect_result = await self.detect_and_mark(
                db, lookback_days=400, persist=persist
            )
            # detect_and_mark also clears; report total cleared from this call path.
            cleared = max(cleared, int(redetect_result.get("cleared_false_transfers") or 0))
        return {
            "cleared": cleared,
            "examined": len(rows_before),
            "redetect": redetect_result,
            "message": (
                f"Cleared {cleared} false transfer flag(s). "
                "True own-account pairs and internal wording were kept."
            ),
        }

    async def resolve_review(
        self,
        db: AsyncSession,
        *,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Resolve transfer-review rows that are no longer transfers.

        Cross-scope pairs keep ``needs_review`` until manually categorised when
        they are still valid internal moves. False-positive transfer marks are
        cleared via ``unmark_false_transfers``.
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
