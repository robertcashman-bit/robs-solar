"""Liability mirroring must not leave duplicate active debts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.db.models import FinanceAccountRow, FinanceLiabilityRow
from app.db.session import SessionLocal
from app.schemas.finance import DebtType, FinanceAccountType, FinanceScope
from app.services.finance.finance_calc import AccountView, compute_totals, liabilities_from_schema
from app.services.finance.finance_liabilities_service import (
    _normalise_debt_name,
    finance_liabilities_service,
)
from app.services.finance.finance_totals import net_worth_debt_gbp


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _add_account(
    db,
    *,
    name: str,
    account_type: str = FinanceAccountType.CREDIT_CARD.value,
    balance: float = 500.0,
    scope: str = FinanceScope.PERSONAL.value,
    interest_rate_pct: float | None = 19.9,
    minimum_payment_gbp: float | None = 25.0,
) -> FinanceAccountRow:
    row = FinanceAccountRow(
        scope=scope,
        account_type=account_type,
        name=name,
        provider="",
        balance_gbp=balance,
        interest_rate_pct=interest_rate_pct,
        minimum_payment_gbp=minimum_payment_gbp,
        notes="",
        source="manual",
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _add_liability(
    db,
    *,
    name: str,
    balance: float = 500.0,
    account_id: int | None = None,
    debt_type: str = DebtType.CREDIT_CARD.value,
    scope: str = FinanceScope.PERSONAL.value,
    interest_rate_pct: float = 19.9,
    minimum_payment_gbp: float = 25.0,
    notes: str = "",
) -> FinanceLiabilityRow:
    row = FinanceLiabilityRow(
        scope=scope,
        name=name,
        debt_type=debt_type,
        balance_gbp=balance,
        interest_rate_pct=interest_rate_pct,
        minimum_payment_gbp=minimum_payment_gbp,
        overpayment_gbp=0,
        original_balance_gbp=balance,
        account_id=account_id,
        notes=notes,
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@pytest.mark.asyncio
async def test_same_account_id_twice_collapses_to_one(setup_db: None) -> None:
    async with SessionLocal() as db:
        account = await _add_account(db, name="MBNA")
        first = await _add_liability(db, name="MBNA", account_id=account.id, balance=400)
        second = await _add_liability(
            db, name="MBNA Card", account_id=account.id, balance=400, notes="From account"
        )

        archived = await finance_liabilities_service.dedupe_active_liabilities(db)
        assert archived == 1

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert len(active) == 1
        assert active[0].account_id == account.id
        assert active[0].id in {first.id, second.id}

        inactive = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(False))
            )
        ).all()
        assert len(inactive) == 1


@pytest.mark.asyncio
async def test_manual_and_mirrored_same_name_become_one_linked(setup_db: None) -> None:
    async with SessionLocal() as db:
        account = await _add_account(db, name="Barclaycard", balance=800)
        manual = await _add_liability(
            db,
            name="Barclaycard!",
            balance=750,
            account_id=None,
            interest_rate_pct=22.9,
            minimum_payment_gbp=30,
            notes="Manual entry",
        )

        created = await finance_liabilities_service.ensure_from_accounts(db)
        assert created == 0

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert len(active) == 1
        assert active[0].id == manual.id
        assert active[0].account_id == account.id
        assert active[0].balance_gbp == 800.0
        assert active[0].interest_rate_pct == 22.9


@pytest.mark.asyncio
async def test_ensure_from_accounts_is_idempotent(setup_db: None) -> None:
    async with SessionLocal() as db:
        await _add_account(db, name="Amex", balance=200)
        first = await finance_liabilities_service.ensure_from_accounts(db)
        second = await finance_liabilities_service.ensure_from_accounts(db)
        assert first == 1
        assert second == 0

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert len(active) == 1
        assert active[0].account_id is not None


@pytest.mark.asyncio
async def test_different_names_stay_separate(setup_db: None) -> None:
    async with SessionLocal() as db:
        await _add_liability(db, name="MBNA", balance=300)
        await _add_liability(db, name="Barclaycard", balance=400)

        archived = await finance_liabilities_service.dedupe_active_liabilities(db)
        assert archived == 0

        listed = await finance_liabilities_service.list_liabilities(db)
        names = sorted(item.name for item in listed)
        assert names == ["Barclaycard", "MBNA"]


@pytest.mark.asyncio
async def test_list_liabilities_archives_existing_duplicates(setup_db: None) -> None:
    async with SessionLocal() as db:
        account = await _add_account(db, name="Capital on Tap", balance=1000)
        await _add_liability(
            db,
            name="Capital on Tap",
            balance=1000,
            account_id=account.id,
            debt_type=DebtType.BUSINESS_LOAN.value,
            notes="From account",
        )
        await _add_liability(
            db,
            name="capital-on-tap",
            balance=1000,
            account_id=None,
            debt_type=DebtType.BUSINESS_LOAN.value,
            notes="Older manual",
        )

        listed = await finance_liabilities_service.list_liabilities(db)
        assert len(listed) == 1
        assert listed[0].account_id == account.id


@pytest.mark.asyncio
async def test_totals_do_not_double_count_after_dedupe(setup_db: None) -> None:
    async with SessionLocal() as db:
        account = await _add_account(db, name="MBNA", balance=500)
        await _add_liability(db, name="MBNA", balance=500, account_id=None)
        await finance_liabilities_service.ensure_from_accounts(db)

        liabilities = await finance_liabilities_service.list_liabilities(db)
        assert len(liabilities) == 1
        assert liabilities[0].account_id == account.id

        account_view = AccountView(
            id=account.id,
            scope="personal",
            account_type="credit_card",
            name="MBNA",
            balance_gbp=500.0,
        )
        totals = compute_totals([account_view], liabilities_from_schema(liabilities))
        assert totals.personal_debt_gbp == 500
        assert totals.credit_card_gbp == 500

        from app.schemas.finance import FinanceAccount, FinanceAccountSource

        schema_account = FinanceAccount(
            id=account.id,
            scope=FinanceScope.PERSONAL,
            account_type=FinanceAccountType.CREDIT_CARD,
            name="MBNA",
            provider="",
            balance_gbp=500.0,
            source=FinanceAccountSource.MANUAL,
            is_active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        # Linked account + liability must not inflate net-worth debt.
        assert net_worth_debt_gbp([schema_account], liabilities) == 500


def test_normalise_debt_name_collapses_punctuation() -> None:
    assert _normalise_debt_name("Capital on Tap!") == _normalise_debt_name("capital-on-tap")
    assert _normalise_debt_name("  MBNA   Card ") == "mbna card"
