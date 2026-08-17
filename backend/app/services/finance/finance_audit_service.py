"""Persistent audit of financial field changes. No invented values."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceChangeAuditRow


class FinanceAuditService:
    async def record(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str = "",
        field: str,
        previous_value: object,
        new_value: object,
        actor: str,
        commit: bool = False,
    ) -> None:
        db.add(
            FinanceChangeAuditRow(
                entity_type=entity_type,
                entity_id=str(entity_id),
                field=field,
                previous_value="" if previous_value is None else str(previous_value),
                new_value="" if new_value is None else str(new_value),
                actor=actor,
                created_at=datetime.now(timezone.utc),
            )
        )
        if commit:
            await db.commit()

    async def list_recent(
        self, db: AsyncSession, *, limit: int = 50
    ) -> list[FinanceChangeAuditRow]:
        rows = await db.scalars(
            select(FinanceChangeAuditRow)
            .order_by(FinanceChangeAuditRow.created_at.desc())
            .limit(limit)
        )
        return list(rows.all())


finance_audit_service = FinanceAuditService()
