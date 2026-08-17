"""Finance liability CRUD."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow, FinanceLiabilityRow
from app.schemas.finance import (
    DebtType,
    FinanceLiability,
    FinanceLiabilityCreate,
    FinanceLiabilityUpdate,
    FinanceScope,
)

ACCOUNT_DEBT_TYPES = {
    "credit_card": DebtType.CREDIT_CARD,
    "loan": DebtType.LOAN,
    "mortgage": DebtType.MORTGAGE,
    "capital_on_tap": DebtType.BUSINESS_LOAN,
    "creditors": DebtType.OTHER,
    "directors_loan": DebtType.DIRECTORS_LOAN,
}


def _to_schema(row: FinanceLiabilityRow) -> FinanceLiability:
    return FinanceLiability(
        id=row.id,
        scope=FinanceScope(row.scope),
        name=row.name,
        debt_type=DebtType(row.debt_type),
        balance_gbp=row.balance_gbp,
        interest_rate_pct=row.interest_rate_pct,
        minimum_payment_gbp=row.minimum_payment_gbp,
        overpayment_gbp=row.overpayment_gbp,
        original_balance_gbp=row.original_balance_gbp,
        payment_day=row.payment_day,
        account_id=row.account_id,
        notes=row.notes,
        dla_direction=row.dla_direction,
        interest_rate_known=(
            True
            if getattr(row, "interest_rate_known", True) is None
            else bool(getattr(row, "interest_rate_known", True))
        ),
        credit_limit_gbp=getattr(row, "credit_limit_gbp", None),
        is_active=row.is_active,
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
        sync_accounts: bool = False,
    ) -> list[FinanceLiability]:
        if sync_accounts:
            from app.services.finance.finance_live_refresh_service import (
                finance_live_refresh_service,
            )

            await finance_live_refresh_service.ensure_fresh(db)
            await self.ensure_from_accounts(db)
        stmt = select(FinanceLiabilityRow).order_by(FinanceLiabilityRow.balance_gbp.desc())
        if scope is not None:
            stmt = stmt.where(FinanceLiabilityRow.scope == scope.value)
        if active_only:
            stmt = stmt.where(FinanceLiabilityRow.is_active.is_(True))
        rows = await db.scalars(stmt)
        return [_to_schema(r) for r in rows.all()]

    async def ensure_from_accounts(self, db: AsyncSession) -> int:
        """Mirror loan-like accounts onto the Debts list, linked to avoid double-count."""
        accounts = (
            await db.scalars(
                select(FinanceAccountRow).where(FinanceAccountRow.is_active.is_(True))
            )
        ).all()
        liabilities = (await db.scalars(select(FinanceLiabilityRow))).all()
        by_account_id = {row.account_id: row for row in liabilities if row.account_id}
        unmatched = [
            row
            for row in liabilities
            if row.account_id is None and row.is_active
        ]
        created = 0
        now = datetime.now(timezone.utc)
        for account in accounts:
            debt_type = ACCOUNT_DEBT_TYPES.get(account.account_type)
            if debt_type is None:
                continue
            balance = round(abs(account.balance_gbp or 0), 2)
            row = by_account_id.get(account.id)
            if row is None:
                account_name = account.name.strip().lower()
                for candidate in unmatched:
                    if (
                        candidate.scope == account.scope
                        and candidate.name.strip().lower() == account_name
                    ):
                        row = candidate
                        row.account_id = account.id
                        unmatched.remove(candidate)
                        break
            if debt_type != DebtType.DIRECTORS_LOAN and balance <= 0:
                if row is not None and row.is_active:
                    row.balance_gbp = 0
                    row.updated_at = now
                continue
            if row is None:
                db.add(
                    FinanceLiabilityRow(
                        scope=account.scope,
                        name=account.name,
                        debt_type=debt_type.value,
                        balance_gbp=balance,
                        interest_rate_pct=account.interest_rate_pct or 0,
                        minimum_payment_gbp=account.minimum_payment_gbp or 0,
                        original_balance_gbp=balance,
                        account_id=account.id,
                        notes="From account",
                        dla_direction=getattr(account, "dla_direction", None),
                        credit_limit_gbp=getattr(account, "credit_limit_gbp", None),
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
                created += 1
                continue
            row.balance_gbp = balance
            row.is_active = True
            if account.interest_rate_pct and not row.interest_rate_pct:
                row.interest_rate_pct = account.interest_rate_pct
            if account.minimum_payment_gbp and not row.minimum_payment_gbp:
                row.minimum_payment_gbp = account.minimum_payment_gbp
            if getattr(account, "dla_direction", None) and not row.dla_direction:
                row.dla_direction = account.dla_direction
            if getattr(account, "credit_limit_gbp", None) and not row.credit_limit_gbp:
                row.credit_limit_gbp = account.credit_limit_gbp
            row.updated_at = now
        await db.commit()
        return created

    async def archive_for_account(self, db: AsyncSession, account_id: int) -> None:
        row = await db.scalar(
            select(FinanceLiabilityRow).where(FinanceLiabilityRow.account_id == account_id)
        )
        if row is None:
            return
        row.is_active = False
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()

    async def get(self, db: AsyncSession, liability_id: int) -> FinanceLiability | None:
        row = await db.get(FinanceLiabilityRow, liability_id)
        return _to_schema(row) if row else None

    async def create(self, db: AsyncSession, body: FinanceLiabilityCreate) -> FinanceLiability:
        if body.account_id is not None:
            existing = await db.scalar(
                select(FinanceLiabilityRow).where(
                    FinanceLiabilityRow.account_id == body.account_id,
                    FinanceLiabilityRow.is_active.is_(True),
                )
            )
            if existing is not None:
                return await self.update(
                    db,
                    existing.id,
                    FinanceLiabilityUpdate(
                        name=body.name,
                        balance_gbp=body.balance_gbp,
                        interest_rate_pct=body.interest_rate_pct,
                        minimum_payment_gbp=body.minimum_payment_gbp,
                        overpayment_gbp=body.overpayment_gbp,
                        original_balance_gbp=body.original_balance_gbp,
                        payment_day=body.payment_day,
                        notes=body.notes,
                    ),
                ) or _to_schema(existing)
        now = datetime.now(timezone.utc)
        row = FinanceLiabilityRow(
            scope=body.scope.value,
            name=body.name,
            debt_type=body.debt_type.value,
            balance_gbp=body.balance_gbp,
            interest_rate_pct=body.interest_rate_pct,
            minimum_payment_gbp=body.minimum_payment_gbp,
            overpayment_gbp=body.overpayment_gbp,
            original_balance_gbp=body.original_balance_gbp
            if body.original_balance_gbp is not None
            else body.balance_gbp,
            payment_day=body.payment_day,
            account_id=body.account_id,
            notes=body.notes,
            dla_direction=body.dla_direction.value if body.dla_direction else None,
            interest_rate_known=body.interest_rate_known,
            credit_limit_gbp=body.credit_limit_gbp,
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
        liability_id: int,
        body: FinanceLiabilityUpdate,
    ) -> FinanceLiability | None:
        row = await db.get(FinanceLiabilityRow, liability_id)
        if row is None:
            return None
        for field, value in body.model_dump(exclude_unset=True).items():
            if hasattr(value, "value"):
                value = value.value
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

    def total_debt(
        self, liabilities: list[FinanceLiability], scope: FinanceScope | None = None
    ) -> float:
        items = liabilities
        if scope is not None:
            items = [debt for debt in liabilities if debt.scope == scope]
        return sum(debt.balance_gbp for debt in items)


finance_liabilities_service = FinanceLiabilitiesService()
