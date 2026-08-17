"""Data-quality checks. Never auto-deletes financial records."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceTransactionRow
from app.services.finance.finance_ledger_service import finance_ledger_service
from app.services.finance.money import from_pence

_PERSONAL_HINTS = ("TESCO", "NETFLIX", "SPOTIFY", "COUNCIL TAX", "SAINSBURY")
_BUSINESS_HINTS = ("HMRC", "COMPANIES HOUSE", "SRA", "LEXIS", "WESTLAW", "FUNDING CIRCLE")


class FinanceDataQualityService:
    async def report(self, db: AsyncSession, *, limit: int = 50) -> dict[str, Any]:
        rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow)
                    .where(FinanceTransactionRow.is_deleted.is_(False))
                    .order_by(FinanceTransactionRow.posted_on.desc())
                    .limit(5000)
                )
            ).all()
        )
        uncategorised = [row for row in rows if not (row.category or "").strip()]
        transfers_review = [row for row in rows if row.subcategory == "needs_review"]
        missing_dates = [row for row in rows if not row.posted_on]

        buckets: dict[tuple[str, int, str], list[FinanceTransactionRow]] = defaultdict(list)
        for row in rows:
            key = (row.posted_on, row.amount_pence, (row.description or "").strip().upper())
            buckets[key].append(row)
        duplicate_candidates = [
            [finance_ledger_service.to_public(item) for item in group]
            for group in buckets.values()
            if len(group) > 1
        ][:limit]

        amounts = [abs(row.amount_pence) for row in rows]
        large: list[dict[str, Any]] = []
        if amounts:
            amounts_sorted = sorted(amounts)
            p95 = amounts_sorted[int(len(amounts_sorted) * 0.95)]
            for row in rows:
                if abs(row.amount_pence) >= max(p95, 50_000):
                    large.append(finance_ledger_service.to_public(row))
                    if len(large) >= limit:
                        break

        wrong_scope: list[dict[str, Any]] = []
        for row in rows:
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

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "transaction_count": len(rows),
            "uncategorised_count": len(uncategorised),
            "uncategorised": [
                finance_ledger_service.to_public(row) for row in uncategorised[:limit]
            ],
            "transfer_review_count": len(transfers_review),
            "transfer_review": [
                finance_ledger_service.to_public(row) for row in transfers_review[:limit]
            ],
            "missing_dates_count": len(missing_dates),
            "duplicate_candidate_groups": duplicate_candidates,
            "large_transactions": large,
            "possible_wrong_scope": wrong_scope,
            "message": "Issues are reported only — records are never auto-deleted.",
            "money_sample_gbp": from_pence(sum(row.amount_pence for row in rows[:20])),
        }


finance_data_quality_service = FinanceDataQualityService()
