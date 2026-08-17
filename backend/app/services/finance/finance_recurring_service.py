"""Propose recurring payees from the ledger. User must confirm or reject."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceRecurringRuleRow, FinanceTransactionRow
from app.services.finance.finance_audit_service import finance_audit_service
from app.services.finance.money import from_pence, to_pence

_NORMALIZE = re.compile(r"[^A-Z0-9]+")
MIN_OCCURRENCES = 3
AMOUNT_TOLERANCE_PENCE = 100


def _payee_key(description: str) -> str:
    return _NORMALIZE.sub(" ", (description or "").upper()).strip()


def _cadence(dates: list[str]) -> str | None:
    parsed = sorted({item for item in dates if item})
    if len(parsed) < MIN_OCCURRENCES:
        return None
    days = []
    for index in range(1, len(parsed)):
        delta = (
            datetime.fromisoformat(parsed[index]).date()
            - datetime.fromisoformat(parsed[index - 1]).date()
        ).days
        days.append(delta)
    if not days:
        return None
    typical = sorted(days)[len(days) // 2]
    if 5 <= typical <= 10:
        return "weekly"
    if 26 <= typical <= 35:
        return "monthly"
    if 13 <= typical <= 17:
        return "fortnightly"
    return None


class FinanceRecurringService:
    async def detect(self, db: AsyncSession, scope: str | None = None) -> list[dict[str, Any]]:
        stmt = select(FinanceTransactionRow).where(
            FinanceTransactionRow.is_deleted.is_(False),
            FinanceTransactionRow.is_transfer.is_(False),
        )
        if scope in {"personal", "business"}:
            stmt = stmt.where(FinanceTransactionRow.scope == scope)
        rows = list((await db.scalars(stmt)).all())
        groups: dict[tuple[str, str, int], list[FinanceTransactionRow]] = defaultdict(list)
        for row in rows:
            key = _payee_key(row.description)
            if not key:
                continue
            bucket = int(round(abs(row.amount_pence) / AMOUNT_TOLERANCE_PENCE))
            groups[(row.scope, key, bucket)].append(row)

        existing = list((await db.scalars(select(FinanceRecurringRuleRow))).all())
        existing_keys = {
            (
                item.scope,
                _payee_key(item.description),
                int(round(abs(to_pence(item.amount_gbp) or 0) / AMOUNT_TOLERANCE_PENCE)),
            )
            for item in existing
        }
        proposed: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for (item_scope, key, bucket), group in groups.items():
            if (item_scope, key, bucket) in existing_keys:
                continue
            cadence = _cadence([row.posted_on for row in group])
            if cadence is None:
                continue
            amounts = [abs(row.amount_pence) for row in group]
            typical = int(round(sum(amounts) / len(amounts)))
            row = FinanceRecurringRuleRow(
                scope=item_scope,
                description=group[0].description[:256],
                amount_gbp=from_pence(typical),
                cadence=cadence,
                category=next((item.category for item in group if item.category), ""),
                status="proposed",
                evidence_json=json.dumps(
                    {
                        "occurrences": len(group),
                        "dates": [item.posted_on for item in group][:12],
                        "payee_key": key,
                    }
                ),
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            proposed.append(self.to_public(row))
        if proposed:
            await db.commit()
        return proposed

    async def list_rules(self, db: AsyncSession, scope: str | None = None) -> list[dict[str, Any]]:
        stmt = select(FinanceRecurringRuleRow).order_by(FinanceRecurringRuleRow.updated_at.desc())
        if scope in {"personal", "business"}:
            stmt = stmt.where(FinanceRecurringRuleRow.scope == scope)
        rows = (await db.scalars(stmt)).all()
        return [self.to_public(row) for row in rows]

    async def set_status(
        self, db: AsyncSession, rule_id: int, status: str, *, actor: str = "user"
    ) -> dict[str, Any] | None:
        if status not in {"confirmed", "rejected", "proposed"}:
            raise ValueError("Status must be confirmed, rejected, or proposed")
        row = await db.get(FinanceRecurringRuleRow, rule_id)
        if row is None:
            return None
        previous = row.status
        row.status = status
        row.updated_at = datetime.now(timezone.utc)
        await finance_audit_service.record(
            db,
            entity_type="recurring_rule",
            entity_id=str(row.id),
            field="status",
            previous_value=previous,
            new_value=status,
            actor=actor,
        )
        await db.commit()
        return self.to_public(row)

    def to_public(self, row: FinanceRecurringRuleRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "scope": row.scope,
            "description": row.description,
            "amount_gbp": row.amount_gbp,
            "cadence": row.cadence,
            "category": row.category,
            "status": row.status,
            "evidence_json": row.evidence_json,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


finance_recurring_service = FinanceRecurringService()
