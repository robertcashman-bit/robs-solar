"""Finance liability CRUD."""

from __future__ import annotations

import re
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
    from app.services.finance.finance_calc import sanitize_mortgage_original_balance

    return FinanceLiability(
        id=row.id,
        scope=FinanceScope(row.scope),
        name=row.name,
        debt_type=DebtType(row.debt_type),
        balance_gbp=row.balance_gbp,
        interest_rate_pct=row.interest_rate_pct,
        minimum_payment_gbp=row.minimum_payment_gbp,
        overpayment_gbp=row.overpayment_gbp,
        original_balance_gbp=sanitize_mortgage_original_balance(
            row.debt_type, row.original_balance_gbp
        ),
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


_LAST4_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")

# Last-4 fingerprinting is for card duplicates only (not loans/mortgages/years).
_CARD_LIKE_DEBT_TYPES = frozenset({DebtType.CREDIT_CARD.value})


def _normalise_debt_name(name: str) -> str:
    """Collapse punctuation/whitespace so near-identical debt names match."""
    cleaned = re.sub(r"[^a-z0-9]+", " ", (name or "").casefold())
    return " ".join(cleaned.split())


def _extract_last4(name: str) -> str | None:
    """Return the last 4-digit token in a debt/account name, if any."""
    matches = _LAST4_RE.findall(name or "")
    if not matches:
        return None
    return matches[-1]


def _is_card_like_debt(debt_type: str) -> bool:
    return debt_type in _CARD_LIKE_DEBT_TYPES


def _name_specificity(name: str) -> tuple[int, int]:
    """Prefer longer / brand-bearing names (e.g. Lloyds … 6754 over bare 6754)."""
    normalised = _normalise_debt_name(name)
    brand_tokens = sum(1 for token in normalised.split() if not token.isdigit())
    return (brand_tokens, len(normalised))


def _balance_key(balance: float | None) -> float:
    return round(float(balance or 0), 2)


def _liability_richness(row: FinanceLiabilityRow) -> tuple[int, int, int]:
    """Prefer rows with more useful payoff metadata when choosing a keeper."""
    has_apr = bool(getattr(row, "interest_rate_known", True) and (row.interest_rate_pct or 0))
    has_minimum = 1 if (row.minimum_payment_gbp or 0) > 0 else 0
    notes = (row.notes or "").strip()
    has_notes = 1 if notes and notes != "From account" else 0
    return (1 if has_apr else 0, has_minimum, has_notes)


def _prefer_liability(
    left: FinanceLiabilityRow, right: FinanceLiabilityRow
) -> FinanceLiabilityRow:
    """Prefer more specific name, then account-linked, richer metadata, older id."""
    left_name = _name_specificity(left.name)
    right_name = _name_specificity(right.name)
    if left_name != right_name:
        return left if left_name > right_name else right
    left_linked = left.account_id is not None
    right_linked = right.account_id is not None
    if left_linked != right_linked:
        return left if left_linked else right
    left_score = _liability_richness(left)
    right_score = _liability_richness(right)
    if left_score != right_score:
        return left if left_score > right_score else right
    left_id = left.id if left.id is not None else 0
    right_id = right.id if right.id is not None else 0
    return left if left_id <= right_id else right


def _aware_updated_at(row: FinanceLiabilityRow) -> datetime:
    value = row.updated_at
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _merge_liability_fields(keeper: FinanceLiabilityRow, donor: FinanceLiabilityRow) -> None:
    """Copy missing useful fields from an archived duplicate onto the keeper."""
    # Keep the fresher balance so a richer stale duplicate cannot win on metadata
    # and leave an outdated amount on the surviving row.
    if _aware_updated_at(donor) > _aware_updated_at(keeper):
        keeper.balance_gbp = donor.balance_gbp
    if not keeper.interest_rate_pct and donor.interest_rate_pct:
        keeper.interest_rate_pct = donor.interest_rate_pct
    if getattr(keeper, "interest_rate_known", True) is False and getattr(
        donor, "interest_rate_known", True
    ):
        keeper.interest_rate_known = True
        if donor.interest_rate_pct:
            keeper.interest_rate_pct = donor.interest_rate_pct
    if not keeper.minimum_payment_gbp and donor.minimum_payment_gbp:
        keeper.minimum_payment_gbp = donor.minimum_payment_gbp
    if not keeper.overpayment_gbp and donor.overpayment_gbp:
        keeper.overpayment_gbp = donor.overpayment_gbp
    if keeper.original_balance_gbp is None and donor.original_balance_gbp is not None:
        keeper.original_balance_gbp = donor.original_balance_gbp
    if keeper.payment_day is None and donor.payment_day is not None:
        keeper.payment_day = donor.payment_day
    if keeper.account_id is None and donor.account_id is not None:
        keeper.account_id = donor.account_id
    if not keeper.dla_direction and donor.dla_direction:
        keeper.dla_direction = donor.dla_direction
    if keeper.credit_limit_gbp is None and donor.credit_limit_gbp is not None:
        keeper.credit_limit_gbp = donor.credit_limit_gbp
    donor_notes = (donor.notes or "").strip()
    keeper_notes = (keeper.notes or "").strip()
    if donor_notes and (not keeper_notes or keeper_notes == "From account"):
        if donor_notes != "From account":
            keeper.notes = donor.notes


def _debt_types_compatible(left: str, right: str) -> bool:
    if left == right:
        return True
    if left == DebtType.OTHER.value or right == DebtType.OTHER.value:
        return True
    loanish = {DebtType.LOAN.value, DebtType.BUSINESS_LOAN.value}
    return left in loanish and right in loanish


def _name_dedupe_account_compatible(
    left: FinanceLiabilityRow, right: FinanceLiabilityRow
) -> bool:
    """Name dedupe may link manual↔mirrored, but not two distinct accounts."""
    if left.account_id is not None and right.account_id is not None:
        return left.account_id == right.account_id
    return True


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
        else:
            # One-shot cleanup so production duplicates disappear on normal reads.
            await self.dedupe_active_liabilities(db)
        stmt = select(FinanceLiabilityRow).order_by(FinanceLiabilityRow.balance_gbp.desc())
        if scope is not None:
            stmt = stmt.where(FinanceLiabilityRow.scope == scope.value)
        if active_only:
            stmt = stmt.where(FinanceLiabilityRow.is_active.is_(True))
        rows = await db.scalars(stmt)
        return [_to_schema(r) for r in rows.all()]

    def _archive_group_onto_keeper(
        self,
        group: list[FinanceLiabilityRow],
        *,
        now: datetime,
    ) -> int:
        """Collapse ``group`` onto one preferred keeper; archive the rest."""
        if len(group) < 2:
            return 0
        keeper = group[0]
        for candidate in group[1:]:
            keeper = _prefer_liability(keeper, candidate)
        archived = 0
        for row in group:
            if row.id == keeper.id:
                continue
            _merge_liability_fields(keeper, row)
            row.is_active = False
            row.updated_at = now
            archived += 1
        keeper.updated_at = now
        return archived

    async def dedupe_active_liabilities(self, db: AsyncSession) -> int:
        """Archive duplicate active debts. Never hard-deletes.

        Rules:
        * one active liability per linked ``account_id``
        * near-duplicates with the same scope + normalised name (compatible
          debt_type) collapse onto the preferred row, but never collapse two
          rows linked to different ``account_id`` values when matching by name
          alone
        * card-like rows that share scope + last-4 + balance (2dp) + compatible
          debt_type collapse even when ``account_id`` / names differ
        """
        rows = list(
            (
                await db.scalars(
                    select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
                )
            ).all()
        )
        if not rows:
            return 0

        archived = 0
        now = datetime.now(timezone.utc)
        touched = False

        by_account: dict[int, list[FinanceLiabilityRow]] = {}
        for row in rows:
            if row.account_id is None:
                continue
            by_account.setdefault(row.account_id, []).append(row)

        for group in by_account.values():
            count = self._archive_group_onto_keeper(group, now=now)
            if count:
                archived += count
                touched = True

        active = [row for row in rows if row.is_active]
        by_name: dict[tuple[str, str], list[FinanceLiabilityRow]] = {}
        for row in active:
            key = (row.scope, _normalise_debt_name(row.name))
            by_name.setdefault(key, []).append(row)

        for group in by_name.values():
            if len(group) < 2:
                continue
            # Partition by compatible debt type so e.g. mortgage + card stay separate.
            # Also keep distinct linked accounts apart even when names match.
            clusters: list[list[FinanceLiabilityRow]] = []
            for row in group:
                placed = False
                for cluster in clusters:
                    if not _debt_types_compatible(cluster[0].debt_type, row.debt_type):
                        continue
                    if not all(
                        _name_dedupe_account_compatible(existing, row)
                        for existing in cluster
                    ):
                        continue
                    cluster.append(row)
                    placed = True
                    break
                if not placed:
                    clusters.append([row])
            for cluster in clusters:
                count = self._archive_group_onto_keeper(cluster, now=now)
                if count:
                    archived += count
                    touched = True

        # Last-4 fingerprint: same card ending + same balance can appear under
        # different account_ids / truncated names (e.g. Lloyds … 6754 vs 6754).
        # Only card-like debts participate so years/loan suffixes cannot collapse.
        active = [row for row in rows if row.is_active]
        by_last4: dict[tuple[str, str, float], list[FinanceLiabilityRow]] = {}
        for row in active:
            if not _is_card_like_debt(row.debt_type):
                continue
            last4 = _extract_last4(row.name)
            if last4 is None:
                continue
            key = (row.scope, last4, _balance_key(row.balance_gbp))
            by_last4.setdefault(key, []).append(row)

        for group in by_last4.values():
            if len(group) < 2:
                continue
            clusters: list[list[FinanceLiabilityRow]] = []
            for row in group:
                placed = False
                for cluster in clusters:
                    # Require compatibility with every member so an `other` seed
                    # cannot bridge incompatible types (e.g. card + mortgage).
                    if not all(
                        _debt_types_compatible(existing.debt_type, row.debt_type)
                        for existing in cluster
                    ):
                        continue
                    cluster.append(row)
                    placed = True
                    break
                if not placed:
                    clusters.append([row])
            for cluster in clusters:
                count = self._archive_group_onto_keeper(cluster, now=now)
                if count:
                    archived += count
                    touched = True

        if touched:
            await db.commit()
        return archived

    async def ensure_from_accounts(self, db: AsyncSession) -> int:
        """Mirror loan-like accounts onto the Debts list, linked to avoid double-count.

        Idempotent: never creates a second liability for an account that already
        has one. Unmatched same-name manual debts are linked before create.
        """
        accounts = (
            await db.scalars(
                select(FinanceAccountRow).where(FinanceAccountRow.is_active.is_(True))
            )
        ).all()
        liabilities = list((await db.scalars(select(FinanceLiabilityRow))).all())

        by_account_id: dict[int, FinanceLiabilityRow] = {}
        for row in liabilities:
            if row.account_id is None:
                continue
            existing = by_account_id.get(row.account_id)
            if existing is None:
                by_account_id[row.account_id] = row
            else:
                # Keep a single preferred row in the lookup; extras are archived later.
                by_account_id[row.account_id] = _prefer_liability(existing, row)

        unmatched = [
            row for row in liabilities if row.account_id is None and row.is_active
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
                account_name = _normalise_debt_name(account.name)
                account_last4 = _extract_last4(account.name)
                match_idx: int | None = None
                match_rank = -1  # higher is better: exact name beats last-4
                for idx, candidate in enumerate(unmatched):
                    if candidate.scope != account.scope:
                        continue
                    if not _debt_types_compatible(candidate.debt_type, debt_type.value):
                        continue
                    name_match = _normalise_debt_name(candidate.name) == account_name
                    # Last-4 linking is card-only; loans/mortgages may share years.
                    last4_match = (
                        debt_type == DebtType.CREDIT_CARD
                        and account_last4 is not None
                        and _extract_last4(candidate.name) == account_last4
                    )
                    if not name_match and not last4_match:
                        continue
                    rank = 2 if name_match else 1
                    if candidate.debt_type == debt_type.value:
                        rank += 1
                    if rank > match_rank:
                        match_idx = idx
                        match_rank = rank
                if match_idx is not None:
                    row = unmatched.pop(match_idx)
                    row.account_id = account.id
                    if _name_specificity(account.name) > _name_specificity(row.name):
                        row.name = account.name
                    by_account_id[account.id] = row
            if debt_type != DebtType.DIRECTORS_LOAN and balance <= 0:
                if row is not None and row.is_active:
                    row.balance_gbp = 0
                    row.updated_at = now
                continue
            if row is None:
                new_row = FinanceLiabilityRow(
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
                db.add(new_row)
                by_account_id[account.id] = new_row
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
        await self.dedupe_active_liabilities(db)
        return created

    async def archive_for_account(self, db: AsyncSession, account_id: int) -> None:
        rows = list(
            (
                await db.scalars(
                    select(FinanceLiabilityRow).where(
                        FinanceLiabilityRow.account_id == account_id,
                        FinanceLiabilityRow.is_active.is_(True),
                    )
                )
            ).all()
        )
        if not rows:
            return
        now = datetime.now(timezone.utc)
        for row in rows:
            row.is_active = False
            row.updated_at = now
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
