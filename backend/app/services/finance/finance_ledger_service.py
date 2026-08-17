"""Query and maintain the stored transaction ledger. Never invent rows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceTransactionRow
from app.services.finance.category_registry import confirm_rule
from app.services.finance.finance_audit_service import finance_audit_service
from app.services.finance.money import from_pence


def _active_tx_filter():
    return FinanceTransactionRow.is_deleted.is_(False)


class FinanceLedgerService:
    async def list_transactions(
        self,
        db: AsyncSession,
        *,
        scope: str | None = None,
        month: str | None = None,
        category: str | None = None,
        account_id: int | None = None,
        include_deleted: bool = False,
        limit: int = 500,
        filter_key: str | None = None,
        q: str | None = None,
        min_amount_gbp: float | None = None,
        max_amount_gbp: float | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        source: str | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        stmt = select(FinanceTransactionRow).order_by(
            FinanceTransactionRow.posted_on.desc(),
            FinanceTransactionRow.id.desc(),
        )
        if not include_deleted:
            stmt = stmt.where(_active_tx_filter())
        if scope in {"personal", "business"}:
            stmt = stmt.where(FinanceTransactionRow.scope == scope)
        if month:
            stmt = stmt.where(FinanceTransactionRow.posted_on.startswith(month))
        if category is not None:
            stmt = stmt.where(FinanceTransactionRow.category == category)
        if account_id is not None:
            stmt = stmt.where(FinanceTransactionRow.account_id == account_id)
        if source:
            stmt = stmt.where(FinanceTransactionRow.source == source)
        if date_from:
            stmt = stmt.where(FinanceTransactionRow.posted_on >= date_from)
        if date_to:
            stmt = stmt.where(FinanceTransactionRow.posted_on <= date_to)

        key = (filter_key or "all").lower()
        if key == "uncategorised":
            stmt = stmt.where(
                or_(
                    FinanceTransactionRow.category == "",
                    FinanceTransactionRow.category.is_(None),
                )
            )
        elif key == "low_confidence":
            stmt = stmt.where(
                or_(
                    func.upper(FinanceTransactionRow.category_confidence) == "LOW",
                    FinanceTransactionRow.category == "",
                    FinanceTransactionRow.category.is_(None),
                )
            )
        elif key == "transfers":
            stmt = stmt.where(FinanceTransactionRow.is_transfer.is_(True))
        elif key == "recurring":
            stmt = stmt.where(FinanceTransactionRow.subcategory.startswith("recurring"))
        elif key == "excluded":
            stmt = stmt.where(FinanceTransactionRow.excluded_from_budget.is_(True))
        elif key == "income":
            stmt = stmt.where(
                FinanceTransactionRow.amount_pence > 0,
                FinanceTransactionRow.is_transfer.is_(False),
            )
        elif key == "expenses":
            stmt = stmt.where(
                FinanceTransactionRow.amount_pence < 0,
                FinanceTransactionRow.is_transfer.is_(False),
            )
        elif key == "needs_review":
            stmt = stmt.where(FinanceTransactionRow.subcategory == "needs_review")

        if q:
            needle = f"%{q.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(FinanceTransactionRow.description).like(needle),
                    func.lower(FinanceTransactionRow.category).like(needle),
                    func.lower(FinanceTransactionRow.account_name).like(needle),
                )
            )
        if min_amount_gbp is not None:
            min_p = abs(int(round(min_amount_gbp * 100)))
            stmt = stmt.where(func.abs(FinanceTransactionRow.amount_pence) >= min_p)
        if max_amount_gbp is not None:
            max_p = abs(int(round(max_amount_gbp * 100)))
            stmt = stmt.where(func.abs(FinanceTransactionRow.amount_pence) <= max_p)

        page = min(max(limit, 1), 200)
        skip = max(offset, 0)
        rows = list((await db.scalars(stmt.offset(skip).limit(page))).all())
        return [self.to_public(row) for row in rows]

    def to_public(self, row: FinanceTransactionRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "scope": row.scope,
            "account_id": row.account_id,
            "account_name": row.account_name,
            "external_id": row.external_id,
            "posted_on": row.posted_on,
            "amount_gbp": from_pence(row.amount_pence),
            "description": row.description,
            "txn_type": row.txn_type,
            "category": row.category,
            "subcategory": row.subcategory,
            "category_confidence": getattr(row, "category_confidence", "") or "",
            "transfer_group_id": getattr(row, "transfer_group_id", None),
            "excluded_from_budget": bool(getattr(row, "excluded_from_budget", False)),
            "notes": getattr(row, "notes", "") or "",
            "source": row.source,
            "import_batch_id": row.import_batch_id,
            "is_transfer": row.is_transfer,
            "is_deleted": row.is_deleted,
            "currency": row.currency,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    async def monthly_flow(
        self,
        db: AsyncSession,
        *,
        days: int = 30,
        scope: str | None = "personal",
        prefer_current: bool = True,
        source: str | None = None,
    ) -> tuple[float, float]:
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
        stmt = select(FinanceTransactionRow).where(
            _active_tx_filter(),
            FinanceTransactionRow.posted_on >= cutoff,
            FinanceTransactionRow.is_transfer.is_(False),
        )
        if scope in {"personal", "business"}:
            stmt = stmt.where(FinanceTransactionRow.scope == scope)
        if source:
            aliases = {
                "lunchflow": ("lunchflow", "lunch_flow"),
                "lunch_flow": ("lunchflow", "lunch_flow"),
            }.get(source, (source,))
            stmt = stmt.where(FinanceTransactionRow.source.in_(aliases))
        rows = list((await db.scalars(stmt)).all())
        if prefer_current:
            current = [row for row in rows if "current" in (row.account_name or "").lower()]
            if current:
                rows = current
        income = sum(row.amount_pence for row in rows if row.amount_pence > 0)
        spending = sum(-row.amount_pence for row in rows if row.amount_pence < 0)
        return from_pence(income), from_pence(spending)

    async def set_category(
        self,
        db: AsyncSession,
        txn_id: int,
        *,
        category: str,
        subcategory: str = "",
        actor: str = "user",
        create_rule: bool = False,
        confidence: str = "HIGH",
    ) -> dict[str, Any] | None:
        row = await db.get(FinanceTransactionRow, txn_id)
        if row is None or row.is_deleted:
            return None
        previous = row.category
        row.category = category[:64]
        row.subcategory = subcategory[:64]
        if hasattr(row, "category_confidence"):
            row.category_confidence = (confidence or "HIGH")[:16]
        row.updated_at = datetime.now(timezone.utc)
        await finance_audit_service.record(
            db,
            entity_type="transaction",
            entity_id=str(row.id),
            field="category",
            previous_value=previous,
            new_value=row.category,
            actor=actor,
        )
        if create_rule and row.description.strip():
            await confirm_rule(
                db,
                pattern=row.description.strip()[:80],
                category=row.category,
                scope=row.scope,
            )
        else:
            await db.commit()
        return self.to_public(row)

    async def bulk_categorise(
        self,
        db: AsyncSession,
        txn_ids: list[int],
        *,
        category: str,
        create_rule: bool = False,
        actor: str = "user",
    ) -> dict[str, Any]:
        updated = 0
        rule_pattern = ""
        for txn_id in txn_ids[:200]:
            row = await db.get(FinanceTransactionRow, txn_id)
            if row is None or row.is_deleted:
                continue
            previous = row.category
            row.category = category[:64]
            if hasattr(row, "category_confidence"):
                row.category_confidence = "HIGH"
            row.updated_at = datetime.now(timezone.utc)
            if not rule_pattern and row.description.strip():
                rule_pattern = row.description.strip()[:80]
            await finance_audit_service.record(
                db,
                entity_type="transaction",
                entity_id=str(row.id),
                field="category",
                previous_value=previous,
                new_value=row.category,
                actor=actor,
            )
            updated += 1
        if create_rule and rule_pattern:
            scope_row = await db.get(FinanceTransactionRow, txn_ids[0])
            await confirm_rule(
                db,
                pattern=rule_pattern,
                category=category[:64],
                scope=scope_row.scope if scope_row else "personal",
            )
        else:
            await db.commit()
        return {"updated": updated, "category": category[:64]}

    async def soft_delete(
        self,
        db: AsyncSession,
        txn_id: int,
        *,
        actor: str = "user",
        confirm: bool = False,
    ) -> bool:
        if not confirm:
            raise ValueError("Confirm is required to delete a transaction")
        row = await db.get(FinanceTransactionRow, txn_id)
        if row is None or row.is_deleted:
            return False
        row.is_deleted = True
        row.updated_at = datetime.now(timezone.utc)
        await finance_audit_service.record(
            db,
            entity_type="transaction",
            entity_id=str(row.id),
            field="is_deleted",
            previous_value="false",
            new_value="true",
            actor=actor,
        )
        await db.commit()
        return True


finance_ledger_service = FinanceLedgerService()
