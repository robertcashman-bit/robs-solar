"""Finance account CRUD."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow, FinanceLiabilityRow
from app.schemas.finance import (
    FinanceAccount,
    FinanceAccountCreate,
    FinanceAccountSource,
    FinanceAccountType,
    FinanceAccountUpdate,
    FinanceScope,
)
from app.services.finance.lunchflow_account_ids import (
    LUNCHFLOW_SOURCES,
    normalize_lunchflow_external_id,
)


def _to_schema(row: FinanceAccountRow) -> FinanceAccount:
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
        source=FinanceAccountSource(row.source),
        external_id=row.external_id,
        dla_direction=row.dla_direction,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _aware_updated_at(row: FinanceAccountRow) -> datetime:
    value = row.updated_at
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _name_quality(name: str) -> tuple[int, int]:
    """Prefer sync-style names (em dash / richer labels) over truncated ones."""
    text = name or ""
    has_separator = 1 if ("—" in text or " - " in text) else 0
    return (has_separator, len(text.strip()))


def _prefer_lunchflow_account(
    left: FinanceAccountRow, right: FinanceAccountRow
) -> FinanceAccountRow:
    """Prefer freshest update, then currently named row, then lower id."""
    left_updated = _aware_updated_at(left)
    right_updated = _aware_updated_at(right)
    if left_updated != right_updated:
        return left if left_updated > right_updated else right
    left_name = _name_quality(left.name)
    right_name = _name_quality(right.name)
    if left_name != right_name:
        return left if left_name > right_name else right
    left_canonical = 1 if left.source == FinanceAccountSource.LUNCHFLOW.value else 0
    right_canonical = 1 if right.source == FinanceAccountSource.LUNCHFLOW.value else 0
    if left_canonical != right_canonical:
        return left if left_canonical > right_canonical else right
    left_id = left.id if left.id is not None else 0
    right_id = right.id if right.id is not None else 0
    return left if left_id <= right_id else right


def _merge_account_fields(keeper: FinanceAccountRow, donor: FinanceAccountRow) -> None:
    """Copy missing useful fields from an archived duplicate onto the keeper."""
    if _aware_updated_at(donor) > _aware_updated_at(keeper):
        keeper.balance_gbp = donor.balance_gbp
        if donor.credit_limit_gbp is not None:
            keeper.credit_limit_gbp = donor.credit_limit_gbp
    if keeper.credit_limit_gbp is None and donor.credit_limit_gbp is not None:
        keeper.credit_limit_gbp = donor.credit_limit_gbp
    if keeper.interest_rate_pct is None and donor.interest_rate_pct is not None:
        keeper.interest_rate_pct = donor.interest_rate_pct
    if keeper.minimum_payment_gbp is None and donor.minimum_payment_gbp is not None:
        keeper.minimum_payment_gbp = donor.minimum_payment_gbp
    if not (keeper.notes or "").strip() and (donor.notes or "").strip():
        keeper.notes = donor.notes
    if not (keeper.provider or "").strip() and (donor.provider or "").strip():
        keeper.provider = donor.provider


class FinanceAccountsService:
    async def list_accounts(
        self,
        db: AsyncSession,
        *,
        scope: FinanceScope | None = None,
        active_only: bool = True,
        refresh_live: bool = False,
    ) -> list[FinanceAccount]:
        # Default reads Neon only so Personal / Business / Reports paint instantly.
        # Live QuickFile / Lunch Flow sync is opt-in via refresh_live=True.
        if refresh_live:
            from app.services.finance.finance_live_refresh_service import (
                finance_live_refresh_service,
            )

            await finance_live_refresh_service.ensure_fresh(db)
        else:
            # One-shot cleanup so production Lunch Flow triples disappear on reads.
            await self.dedupe_active_lunchflow_accounts(db)
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
            dla_direction=body.dla_direction.value if body.dla_direction else None,
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
            if hasattr(value, "value"):
                value = value.value
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

    async def dedupe_active_lunchflow_accounts(self, db: AsyncSession) -> int:
        """Archive duplicate active Lunch Flow accounts. Never hard-deletes.

        Collapses rows that share a normalised external id (``28085`` vs
        ``lunchflow:28085``) and source alias (``lunchflow`` / ``lunch_flow``).
        Keeper preference: most recently updated, then currently named.
        Liabilities linked to archived rows are re-pointed at the keeper so
        overview debt tiles do not double-count cards.
        """
        rows = list(
            (
                await db.scalars(
                    select(FinanceAccountRow).where(
                        FinanceAccountRow.is_active.is_(True),
                        FinanceAccountRow.source.in_(tuple(LUNCHFLOW_SOURCES)),
                    )
                )
            ).all()
        )
        if not rows:
            return 0

        by_key: dict[str, list[FinanceAccountRow]] = {}
        for row in rows:
            key = normalize_lunchflow_external_id(row.external_id)
            if not key:
                continue
            by_key.setdefault(key, []).append(row)

        archived = 0
        touched = False
        now = datetime.now(timezone.utc)
        remaps: list[tuple[int, int]] = []

        for group in by_key.values():
            if len(group) < 2:
                # Still normalise a lone legacy row so later upserts match.
                alone = group[0]
                canonical = normalize_lunchflow_external_id(alone.external_id)
                changed = False
                if alone.external_id != canonical and canonical:
                    alone.external_id = canonical
                    changed = True
                if alone.source != FinanceAccountSource.LUNCHFLOW.value:
                    alone.source = FinanceAccountSource.LUNCHFLOW.value
                    changed = True
                if changed:
                    alone.updated_at = now
                    touched = True
                continue

            keeper = group[0]
            for candidate in group[1:]:
                keeper = _prefer_lunchflow_account(keeper, candidate)
            canonical = normalize_lunchflow_external_id(keeper.external_id)
            for row in group:
                if row.id == keeper.id:
                    continue
                _merge_account_fields(keeper, row)
                row.is_active = False
                row.updated_at = now
                remaps.append((row.id, keeper.id))
                archived += 1
            if keeper.external_id != canonical and canonical:
                keeper.external_id = canonical
            keeper.source = FinanceAccountSource.LUNCHFLOW.value
            keeper.is_active = True
            keeper.updated_at = now
            touched = True

        if remaps:
            await self._repoint_liabilities(db, remaps)
        if touched or archived:
            await db.commit()
        return archived

    async def _repoint_liabilities(
        self, db: AsyncSession, remaps: list[tuple[int, int]]
    ) -> None:
        if not remaps:
            return
        from_ids = [from_id for from_id, _ in remaps]
        to_by_from = {from_id: to_id for from_id, to_id in remaps}
        liabilities = list(
            (
                await db.scalars(
                    select(FinanceLiabilityRow).where(
                        FinanceLiabilityRow.account_id.in_(from_ids)
                    )
                )
            ).all()
        )
        for liability in liabilities:
            account_id = liability.account_id
            if account_id is None:
                continue
            keeper_id = to_by_from.get(account_id)
            if keeper_id is not None:
                liability.account_id = keeper_id

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
            a.balance_gbp
            for a in accounts
            if a.scope == scope and a.account_type == account_type
        )


finance_accounts_service = FinanceAccountsService()
