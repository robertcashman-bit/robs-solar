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
    _extract_last4,
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
async def test_different_account_ids_same_name_stay_separate(setup_db: None) -> None:
    async with SessionLocal() as db:
        first_account = await _add_account(db, name="Loan", balance=1000)
        second_account = await _add_account(
            db,
            name="Loan",
            balance=2000,
            account_type=FinanceAccountType.LOAN.value,
        )
        first = await _add_liability(
            db,
            name="Loan",
            balance=1000,
            account_id=first_account.id,
            debt_type=DebtType.LOAN.value,
            notes="From account",
        )
        second = await _add_liability(
            db,
            name="Loan",
            balance=2000,
            account_id=second_account.id,
            debt_type=DebtType.LOAN.value,
            notes="From account",
        )

        archived = await finance_liabilities_service.dedupe_active_liabilities(db)
        assert archived == 0

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert {row.id for row in active} == {first.id, second.id}
        assert {row.account_id for row in active} == {first_account.id, second_account.id}


@pytest.mark.asyncio
async def test_same_account_dedupe_keeps_fresher_balance(setup_db: None) -> None:
    async with SessionLocal() as db:
        account = await _add_account(db, name="MBNA", balance=350)
        stale = await _add_liability(
            db,
            name="MBNA",
            account_id=account.id,
            balance=900,
            interest_rate_pct=22.9,
            minimum_payment_gbp=40,
            notes="Older manual details",
        )
        stale.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        fresh = await _add_liability(
            db,
            name="MBNA",
            account_id=account.id,
            balance=350,
            interest_rate_pct=0,
            minimum_payment_gbp=0,
            notes="From account",
        )
        fresh.updated_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
        await db.commit()

        archived = await finance_liabilities_service.dedupe_active_liabilities(db)
        assert archived == 1

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert len(active) == 1
        assert active[0].account_id == account.id
        assert active[0].balance_gbp == 350.0
        assert active[0].interest_rate_pct == 22.9
        assert active[0].minimum_payment_gbp == 40
        assert active[0].notes == "Older manual details"


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


def test_extract_last4_from_card_names() -> None:
    assert _extract_last4("Lloyds Personal — 6754 credit card") == "6754"
    assert _extract_last4("6754 credit card") == "6754"
    assert _extract_last4("Loan") is None
    assert _extract_last4("Card 12") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("long_name", "short_name", "balance"),
    [
        ("Lloyds Personal — 6754 credit card", "6754 credit card", 8974.94),
        ("Lloyds Personal — 7946 credit card", "7946 credit card", 7131.92),
    ],
)
async def test_last4_fingerprint_collapses_production_triple(
    setup_db: None,
    long_name: str,
    short_name: str,
    balance: float,
) -> None:
    """Two long names (different account_ids) + short last-4 name → one active."""
    async with SessionLocal() as db:
        first_account = await _add_account(db, name=long_name, balance=balance)
        second_account = await _add_account(db, name=long_name, balance=balance)
        first = await _add_liability(
            db,
            name=long_name,
            balance=balance,
            account_id=first_account.id,
            interest_rate_pct=22.9,
            minimum_payment_gbp=40,
            notes="From account",
        )
        second = await _add_liability(
            db,
            name=long_name,
            balance=balance,
            account_id=second_account.id,
            interest_rate_pct=0,
            minimum_payment_gbp=0,
            notes="From account",
        )
        short = await _add_liability(
            db,
            name=short_name,
            balance=balance,
            account_id=None,
            interest_rate_pct=19.9,
            minimum_payment_gbp=35,
            notes="Manual card",
        )

        archived = await finance_liabilities_service.dedupe_active_liabilities(db)
        assert archived == 2

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert len(active) == 1
        keeper = active[0]
        assert keeper.id in {first.id, second.id, short.id}
        assert keeper.name == long_name
        assert keeper.balance_gbp == balance
        assert keeper.interest_rate_pct in {22.9, 19.9}
        assert (keeper.notes or "").strip() in {"Manual card", "From account"}

        inactive = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(False))
            )
        ).all()
        assert len(inactive) == 2


@pytest.mark.asyncio
async def test_different_last4s_stay_separate(setup_db: None) -> None:
    async with SessionLocal() as db:
        first = await _add_liability(
            db,
            name="Lloyds Personal — 6754 credit card",
            balance=8974.94,
            account_id=None,
        )
        second = await _add_liability(
            db,
            name="Lloyds Personal — 7946 credit card",
            balance=7131.92,
            account_id=None,
        )

        archived = await finance_liabilities_service.dedupe_active_liabilities(db)
        assert archived == 0

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert {row.id for row in active} == {first.id, second.id}


@pytest.mark.asyncio
async def test_last4_different_scopes_stay_separate(setup_db: None) -> None:
    async with SessionLocal() as db:
        personal = await _add_liability(
            db,
            name="Lloyds — 6754 credit card",
            balance=1000,
            scope=FinanceScope.PERSONAL.value,
        )
        business = await _add_liability(
            db,
            name="Lloyds — 6754 credit card",
            balance=1000,
            scope=FinanceScope.BUSINESS.value,
            debt_type=DebtType.CREDIT_CARD.value,
        )

        archived = await finance_liabilities_service.dedupe_active_liabilities(db)
        assert archived == 0

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert {row.id for row in active} == {personal.id, business.id}


@pytest.mark.asyncio
async def test_last4_incompatible_debt_types_stay_separate(setup_db: None) -> None:
    async with SessionLocal() as db:
        card = await _add_liability(
            db,
            name="Account 6754 credit card",
            balance=1000,
            debt_type=DebtType.CREDIT_CARD.value,
        )
        mortgage = await _add_liability(
            db,
            name="Account 6754 mortgage",
            balance=1000,
            debt_type=DebtType.MORTGAGE.value,
        )

        archived = await finance_liabilities_service.dedupe_active_liabilities(db)
        assert archived == 0

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert {row.id for row in active} == {card.id, mortgage.id}


@pytest.mark.asyncio
async def test_last4_other_does_not_bridge_incompatible_types(setup_db: None) -> None:
    """An `other` seed must not pull a card and mortgage into one last-4 cluster."""
    async with SessionLocal() as db:
        other = await _add_liability(
            db,
            name="Account 6754",
            balance=1000,
            debt_type=DebtType.OTHER.value,
        )
        card = await _add_liability(
            db,
            name="Lloyds — 6754 credit card",
            balance=1000,
            debt_type=DebtType.CREDIT_CARD.value,
        )
        mortgage = await _add_liability(
            db,
            name="Mortgage 6754",
            balance=1000,
            debt_type=DebtType.MORTGAGE.value,
        )

        archived = await finance_liabilities_service.dedupe_active_liabilities(db)
        assert archived == 0

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert {row.id for row in active} == {other.id, card.id, mortgage.id}


@pytest.mark.asyncio
async def test_last4_non_card_debts_with_shared_digits_stay_separate(
    setup_db: None,
) -> None:
    """Loans/mortgages sharing a year-like token must not last-4 collapse."""
    async with SessionLocal() as db:
        loan = await _add_liability(
            db,
            name="Personal loan 2024",
            balance=5000,
            debt_type=DebtType.LOAN.value,
        )
        mortgage = await _add_liability(
            db,
            name="House mortgage 2024",
            balance=5000,
            debt_type=DebtType.MORTGAGE.value,
        )

        archived = await finance_liabilities_service.dedupe_active_liabilities(db)
        assert archived == 0

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert {row.id for row in active} == {loan.id, mortgage.id}


@pytest.mark.asyncio
async def test_last4_different_balances_stay_separate(setup_db: None) -> None:
    async with SessionLocal() as db:
        first = await _add_liability(
            db,
            name="Lloyds Personal — 6754 credit card",
            balance=8974.94,
            account_id=None,
        )
        second = await _add_liability(
            db,
            name="6754 credit card",
            balance=5000.0,
            account_id=None,
        )

        archived = await finance_liabilities_service.dedupe_active_liabilities(db)
        assert archived == 0

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert {row.id for row in active} == {first.id, second.id}


@pytest.mark.asyncio
async def test_ensure_links_manual_by_shared_last4(setup_db: None) -> None:
    async with SessionLocal() as db:
        account = await _add_account(
            db,
            name="Lloyds Personal — 6754 credit card",
            balance=8974.94,
        )
        manual = await _add_liability(
            db,
            name="6754 credit card",
            balance=8900.0,
            account_id=None,
            interest_rate_pct=22.9,
            minimum_payment_gbp=40,
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
        assert active[0].balance_gbp == 8974.94
        assert active[0].interest_rate_pct == 22.9
        assert active[0].name == "Lloyds Personal — 6754 credit card"


@pytest.mark.asyncio
async def test_ensure_does_not_last4_link_non_card_account(setup_db: None) -> None:
    """A loan account must not claim a manual row merely via shared digits."""
    async with SessionLocal() as db:
        await _add_account(
            db,
            name="Personal loan 2024",
            balance=5000,
            account_type=FinanceAccountType.LOAN.value,
        )
        manual = await _add_liability(
            db,
            name="Other facility 2024",
            balance=4800,
            account_id=None,
            debt_type=DebtType.LOAN.value,
            notes="Manual loan",
        )

        created = await finance_liabilities_service.ensure_from_accounts(db)
        assert created == 1

        await db.refresh(manual)
        assert manual.account_id is None
        assert manual.name == "Other facility 2024"
        assert manual.balance_gbp == 4800

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert len(active) == 2
        assert {row.account_id is not None for row in active} == {True, False}


@pytest.mark.asyncio
async def test_ensure_does_not_recreate_archived_last4_extras(setup_db: None) -> None:
    async with SessionLocal() as db:
        long_name = "Lloyds Personal — 6754 credit card"
        balance = 8974.94
        first_account = await _add_account(db, name=long_name, balance=balance)
        second_account = await _add_account(db, name=long_name, balance=balance)
        await _add_liability(
            db, name=long_name, balance=balance, account_id=first_account.id
        )
        await _add_liability(
            db, name=long_name, balance=balance, account_id=second_account.id
        )
        await _add_liability(db, name="6754 credit card", balance=balance, account_id=None)

        first = await finance_liabilities_service.ensure_from_accounts(db)
        second = await finance_liabilities_service.ensure_from_accounts(db)
        assert first == 0
        assert second == 0

        active = (
            await db.scalars(
                select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).all()
        assert len(active) == 1
        assert active[0].balance_gbp == balance
        assert "6754" in active[0].name


@pytest.mark.asyncio
async def test_list_liabilities_collapses_last4_without_sync(setup_db: None) -> None:
    async with SessionLocal() as db:
        long_name = "Lloyds Personal — 6754 credit card"
        balance = 8974.94
        first_account = await _add_account(db, name=long_name, balance=balance)
        second_account = await _add_account(db, name=long_name, balance=balance)
        await _add_liability(
            db, name=long_name, balance=balance, account_id=first_account.id
        )
        await _add_liability(
            db, name=long_name, balance=balance, account_id=second_account.id
        )
        await _add_liability(db, name="6754 credit card", balance=balance, account_id=None)

        listed = await finance_liabilities_service.list_liabilities(db)
        assert len(listed) == 1
        assert listed[0].name == long_name
        assert listed[0].balance_gbp == balance
