"""Data-quality checks. Never auto-deletes financial records without an explicit job."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceTransactionRow
from app.services.finance.finance_ledger_service import finance_ledger_service
from app.services.finance.money import from_pence

_PERSONAL_HINTS = ("TESCO", "NETFLIX", "SPOTIFY", "COUNCIL TAX", "SAINSBURY")
_BUSINESS_HINTS = ("HMRC", "COMPANIES HOUSE", "SRA", "LEXIS", "WESTLAW", "FUNDING CIRCLE")


def _active() -> Any:
    return FinanceTransactionRow.is_deleted.is_(False)


class FinanceDataQualityService:
    async def report(self, db: AsyncSession, *, limit: int = 50) -> dict[str, Any]:
        """Full-ledger SQL counts + limited samples (with ids for deep links)."""
        counts_row = (
            await db.execute(
                select(
                    func.count().label("transaction_count"),
                    func.count()
                    .filter(
                        or_(
                            FinanceTransactionRow.category.is_(None),
                            FinanceTransactionRow.category == "",
                        )
                    )
                    .label("uncategorised_count"),
                    func.count()
                    .filter(FinanceTransactionRow.subcategory == "needs_review")
                    .label("transfer_review_count"),
                    func.count()
                    .filter(
                        or_(
                            FinanceTransactionRow.posted_on.is_(None),
                            FinanceTransactionRow.posted_on == "",
                        )
                    )
                    .label("missing_dates_count"),
                    func.count()
                    .filter(FinanceTransactionRow.is_transfer.is_(True))
                    .label("transfer_count"),
                ).where(_active())
            )
        ).one()

        uncategorised_rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow)
                    .where(
                        _active(),
                        or_(
                            FinanceTransactionRow.category.is_(None),
                            FinanceTransactionRow.category == "",
                        ),
                    )
                    .order_by(FinanceTransactionRow.id.desc())
                    .limit(limit)
                )
            ).all()
        )
        transfers_review = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow)
                    .where(
                        _active(),
                        FinanceTransactionRow.subcategory == "needs_review",
                    )
                    .order_by(FinanceTransactionRow.posted_on.desc())
                    .limit(limit)
                )
            ).all()
        )
        missing_dates = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow)
                    .where(
                        _active(),
                        or_(
                            FinanceTransactionRow.posted_on.is_(None),
                            FinanceTransactionRow.posted_on == "",
                        ),
                    )
                    .order_by(FinanceTransactionRow.id.desc())
                    .limit(limit)
                )
            ).all()
        )

        # Duplicate candidates: sample recent dated rows only (expensive group-by
        # stays bounded). Counts above already cover the full ledger.
        sample_rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow)
                    .where(
                        _active(),
                        FinanceTransactionRow.posted_on != "",
                    )
                    .order_by(FinanceTransactionRow.posted_on.desc())
                    .limit(5000)
                )
            ).all()
        )
        buckets: dict[tuple[str, int, str], list[FinanceTransactionRow]] = defaultdict(list)
        for row in sample_rows:
            key = (row.posted_on, row.amount_pence, (row.description or "").strip().upper())
            buckets[key].append(row)
        duplicate_candidates = [
            [finance_ledger_service.to_public(item) for item in group]
            for group in buckets.values()
            if len(group) > 1
        ][:limit]

        amounts = [abs(row.amount_pence) for row in sample_rows]
        large: list[dict[str, Any]] = []
        if amounts:
            amounts_sorted = sorted(amounts)
            p95 = amounts_sorted[int(len(amounts_sorted) * 0.95)]
            for row in sample_rows:
                if abs(row.amount_pence) >= max(p95, 50_000):
                    large.append(finance_ledger_service.to_public(row))
                    if len(large) >= limit:
                        break

        wrong_scope: list[dict[str, Any]] = []
        for row in sample_rows:
            text = (row.description or "").upper()
            if row.scope == "business" and any(hint in text for hint in _PERSONAL_HINTS):
                wrong_scope.append(
                    {
                        **finance_ledger_service.to_public(row),
                        "issue": "possible_personal_on_business",
                    }
                )
            elif row.scope == "personal" and any(hint in text for hint in _BUSINESS_HINTS):
                wrong_scope.append(
                    {
                        **finance_ledger_service.to_public(row),
                        "issue": "possible_business_on_personal",
                    }
                )
            if len(wrong_scope) >= limit:
                break

        def _with_link(row: FinanceTransactionRow) -> dict[str, Any]:
            public = finance_ledger_service.to_public(row)
            public["href"] = f"/finance/transactions?q={row.id}"
            return public

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "transaction_count": int(counts_row.transaction_count or 0),
            "uncategorised_count": int(counts_row.uncategorised_count or 0),
            "uncategorised": [_with_link(row) for row in uncategorised_rows],
            "transfer_review_count": int(counts_row.transfer_review_count or 0),
            "transfer_review": [_with_link(row) for row in transfers_review],
            "missing_dates_count": int(counts_row.missing_dates_count or 0),
            "missing_dates": [_with_link(row) for row in missing_dates],
            "transfer_count": int(counts_row.transfer_count or 0),
            "duplicate_candidate_groups": duplicate_candidates,
            "large_transactions": large,
            "possible_wrong_scope": wrong_scope,
            "full_ledger": True,
            "message": (
                "Counts cover the full ledger via SQL. Samples include deep links. "
                "Records are never auto-deleted from this report alone."
            ),
            "money_sample_gbp": from_pence(sum(row.amount_pence for row in sample_rows[:20])),
            "actions": [
                "backfill-dates",
                "apply-rules",
                "resolve-review",
            ],
        }


finance_data_quality_service = FinanceDataQualityService()
