"""Finance liability CRUD."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceLiabilityRow
from app.schemas.finance import (
    DebtType,
    FinanceLiability,
    FinanceLiabilityCreate,
    FinanceLiabilityUpdate,
    FinanceScope,
)

_HISTORIC_SEED_MARKER = "historic-seed-v1"
_STALE_AFTER = timedelta(days=3)


def _liability_confidence(row: FinanceLiabilityRow, *, is_historic: bool) -> str:
    if is_historic:
        return "historic"
    if row.account_id is not None:
        age = datetime.now(timezone.utc) - row.updated_at
        if age > _STALE_AFTER:
            return "stale"
        return "live"
    return "manual"


def _to_schema(row: FinanceLiabilityRow) -> FinanceLiability:
    is_historic = _HISTORIC_SEED_MARKER in (row.notes or "")
    return FinanceLiability(
        id=row.id,
        scope=FinanceScope(row.scope),
        name=row.name,
        debt_type=DebtType(row.debt_type),
        balance_gbp=row.balance_gbp,
        interest_rate_pct=row.interest_rate_pct,
        minimum_payment_gbp=row.minimum_payment_gbp,
        overpayment_gbp=row.overpayment_gbp,
        payment_day=row.payment_day,
        account_id=row.account_id,
        notes=row.notes,
        is_active=row.is_active,
        is_historic=is_historic,
        data_confidence=_liability_confidence(row, is_historic=is_historic),
        last_synced_at=row.updated_at if row.account_id is not None else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class FinanceLiabilitiesService:
    async def list_liabilities(
        self,
        db: AsyncSession,
        *,
        scope: FinanceScope | None = None,
        active_only: bool = True,
    ) -> list[FinanceLiability]:
        stmt = select(FinanceLiabilityRow).order_by(FinanceLiabilityRow.balance_gbp.desc())
        if scope is not None:
            stmt = stmt.where(FinanceLiabilityRow.scope == scope.value)
        if active_only:
            stmt = stmt.where(FinanceLiabilityRow.is_active.is_(True))
        rows = await db.scalars(stmt)
        return [_to_schema(r) for r in rows.all()]

    async def get(self, db: AsyncSession, liability_id: int) -> FinanceLiability | None:
        row = await db.get(FinanceLiabilityRow, liability_id)
        return _to_schema(row) if row else None

    async def create(self, db: AsyncSession, body: FinanceLiabilityCreate) -> FinanceLiability:
        now = datetime.now(timezone.utc)
        row = FinanceLiabilityRow(
            scope=body.scope.value,
            name=body.name,
            debt_type=body.debt_type.value,
            balance_gbp=body.balance_gbp,
            interest_rate_pct=body.interest_rate_pct,
            minimum_payment_gbp=body.minimum_payment_gbp,
            overpayment_gbp=body.overpayment_gbp,
            payment_day=body.payment_day,
            account_id=body.account_id,
            notes=body.notes,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)

    async def update(
        self, db: AsyncSession, liability_id: int, body: FinanceLiabilityUpdate
    ) -> FinanceLiability | None:
        row = await db.get(FinanceLiabilityRow, liability_id)
        if row is None:
            return None
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)

    async def delete(self, db: AsyncSession, liability_id: int) -> bool:
        row = await db.get(FinanceLiabilityRow, liability_id)
        if row is None:
            return False
        row.is_active = False
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return True


finance_liabilities_service = FinanceLiabilitiesService()
