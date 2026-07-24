"""Finance account CRUD."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow
from app.schemas.finance import (
    FinanceAccount,
    FinanceAccountCreate,
    FinanceAccountSource,
    FinanceAccountType,
    FinanceAccountUpdate,
    FinanceScope,
    account_is_historic,
)

_STALE_AFTER = timedelta(days=3)
_LIVE_SOURCES = {
    FinanceAccountSource.LUNCH_FLOW,
    FinanceAccountSource.OPEN_BANKING,
    FinanceAccountSource.QUICKFILE,
}


def _account_confidence(source: FinanceAccountSource, updated_at: datetime, *, is_historic: bool) -> str:
    if is_historic:
        return "historic"
    if source in _LIVE_SOURCES:
        age = datetime.now(timezone.utc) - updated_at
        if age > _STALE_AFTER:
            return "stale"
        return "live"
    return "manual"


def _to_schema(row: FinanceAccountRow) -> FinanceAccount:
    source = FinanceAccountSource(row.source)
    historic = account_is_historic(source)
    return FinanceAccount(
        id=row.id,
        scope=FinanceScope(row.scope),
        account_type=FinanceAccountType(row.account_type),
        name=row.name,
        provider=row.provider,
        balance_gbp=row.balance_gbp,
        credit_limit_gbp=row.credit_limit_gbp,
        interest_rate_pct=row.interest_rate_pct,
        minimum_payment_gbp=row.minimum_payment_gbp,
        notes=row.notes,
        source=source,
        external_id=row.external_id,
        is_active=row.is_active,
        is_historic=historic,
        data_confidence=_account_confidence(source, row.updated_at, is_historic=historic),
        last_synced_at=row.updated_at if source in _LIVE_SOURCES else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class FinanceAccountsService:
    async def list_accounts(
        self,
        db: AsyncSession,
        *,
        scope: FinanceScope | None = None,
        active_only: bool = True,
    ) -> list[FinanceAccount]:
        stmt = select(FinanceAccountRow).order_by(FinanceAccountRow.name)
        if scope is not None:
            stmt = stmt.where(FinanceAccountRow.scope == scope.value)
        if active_only:
            stmt = stmt.where(FinanceAccountRow.is_active.is_(True))
        rows = await db.scalars(stmt)
        return [_to_schema(r) for r in rows.all()]

    async def get(self, db: AsyncSession, account_id: int) -> FinanceAccount | None:
        row = await db.get(FinanceAccountRow, account_id)
        return _to_schema(row) if row else None

    async def create(self, db: AsyncSession, body: FinanceAccountCreate) -> FinanceAccount:
        now = datetime.now(timezone.utc)
        row = FinanceAccountRow(
            scope=body.scope.value,
            account_type=body.account_type.value,
            name=body.name,
            provider=body.provider,
            balance_gbp=body.balance_gbp,
            credit_limit_gbp=body.credit_limit_gbp,
            interest_rate_pct=body.interest_rate_pct,
            minimum_payment_gbp=body.minimum_payment_gbp,
            notes=body.notes,
            source=body.source.value,
            external_id=body.external_id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)

    async def update(
        self,
        db: AsyncSession,
        account_id: int,
        body: FinanceAccountUpdate,
    ) -> FinanceAccount | None:
        row = await db.get(FinanceAccountRow, account_id)
        if row is None:
            return None
        for field, value in body.model_dump(exclude_unset=True).items():
            if field == "account_type" and value is not None:
                row.account_type = (
                    value.value if isinstance(value, FinanceAccountType) else str(value)
                )
            else:
                setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)

    async def delete(self, db: AsyncSession, account_id: int) -> bool:
        row = await db.get(FinanceAccountRow, account_id)
        if row is None:
            return False
        row.is_active = False
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return True

    def sum_by_type(
        self,
        accounts: list[FinanceAccount],
        account_type: FinanceAccountType,
    ) -> float:
        return sum(a.balance_gbp for a in accounts if a.account_type == account_type)

    def sum_scope_balance(
        self,
        accounts: list[FinanceAccount],
        scope: FinanceScope,
        account_type: FinanceAccountType = FinanceAccountType.CURRENT,
    ) -> float:
        return sum(
            a.balance_gbp for a in accounts if a.scope == scope and a.account_type == account_type
        )


finance_accounts_service = FinanceAccountsService()
