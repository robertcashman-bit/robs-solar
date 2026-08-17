"""User-defined sinking funds. No default Christmas or holiday amounts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceSinkingFundRow
from app.services.finance.finance_audit_service import finance_audit_service
from app.services.finance.money import quantize_gbp


def _months_left(due_on: str, today: date | None = None) -> int:
    today = today or datetime.now(timezone.utc).date()
    due = date.fromisoformat(due_on[:10])
    months = (due.year - today.year) * 12 + (due.month - today.month)
    if due.day < today.day and months > 0:
        months -= 1
    return max(1, months) if due > today else 1


def _contribution(target: float, saved: float, due_on: str) -> dict[str, Any]:
    remaining = quantize_gbp((target or 0) - (saved or 0)) or 0.0
    months = _months_left(due_on)
    monthly = quantize_gbp(remaining / months) if remaining > 0 else 0.0
    return {
        "remaining_gbp": remaining,
        "months_left": months,
        "monthly_contribution_gbp": monthly or 0.0,
        "formula": f"{remaining} / {months}",
    }


class FinanceSinkingFundService:
    async def list_funds(self, db: AsyncSession, scope: str | None = None) -> list[dict[str, Any]]:
        stmt = select(FinanceSinkingFundRow).order_by(FinanceSinkingFundRow.due_on)
        if scope in {"personal", "business"}:
            stmt = stmt.where(FinanceSinkingFundRow.scope == scope)
        rows = (await db.scalars(stmt)).all()
        return [self.to_public(row) for row in rows]

    async def create(
        self, db: AsyncSession, body: dict[str, Any], *, actor: str = "user"
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        due_on = str(body["due_on"])[:10]
        date.fromisoformat(due_on)
        row = FinanceSinkingFundRow(
            scope=str(body["scope"]),
            name=str(body["name"])[:128],
            target_gbp=float(body["target_gbp"]),
            saved_gbp=float(body.get("saved_gbp") or 0),
            due_on=due_on,
            notes=str(body.get("notes") or ""),
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        await finance_audit_service.record(
            db,
            entity_type="sinking_fund",
            entity_id=str(row.id),
            field="create",
            previous_value="",
            new_value=str(row.target_gbp),
            actor=actor,
        )
        await db.commit()
        return self.to_public(row)

    async def update(
        self, db: AsyncSession, fund_id: int, body: dict[str, Any], *, actor: str = "user"
    ) -> dict[str, Any] | None:
        row = await db.get(FinanceSinkingFundRow, fund_id)
        if row is None:
            return None
        for field in ("name", "target_gbp", "saved_gbp", "due_on", "notes"):
            if field not in body or body[field] is None:
                continue
            previous = getattr(row, field)
            value = body[field]
            if field == "due_on":
                value = str(value)[:10]
                date.fromisoformat(value)
            setattr(row, field, value)
            if previous != getattr(row, field):
                await finance_audit_service.record(
                    db,
                    entity_type="sinking_fund",
                    entity_id=str(row.id),
                    field=field,
                    previous_value=previous,
                    new_value=getattr(row, field),
                    actor=actor,
                )
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return self.to_public(row)

    async def delete(
        self, db: AsyncSession, fund_id: int, *, confirm: bool, actor: str = "user"
    ) -> bool:
        if not confirm:
            raise ValueError("Confirm is required to delete a sinking fund")
        row = await db.get(FinanceSinkingFundRow, fund_id)
        if row is None:
            return False
        await finance_audit_service.record(
            db,
            entity_type="sinking_fund",
            entity_id=str(row.id),
            field="delete",
            previous_value=row.name,
            new_value="",
            actor=actor,
        )
        await db.delete(row)
        await db.commit()
        return True

    def to_public(self, row: FinanceSinkingFundRow) -> dict[str, Any]:
        math = _contribution(row.target_gbp, row.saved_gbp, row.due_on)
        return {
            "id": row.id,
            "scope": row.scope,
            "name": row.name,
            "target_gbp": row.target_gbp,
            "saved_gbp": row.saved_gbp,
            "due_on": row.due_on,
            "notes": row.notes,
            **math,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


finance_sinking_fund_service = FinanceSinkingFundService()
