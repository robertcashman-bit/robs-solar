"""Tests for stated personal finance seeds."""

import pytest
from sqlalchemy import select

from app.db.models import AppSettingRow, FinanceAccountRow, FinanceLiabilityRow
from app.db.session import SessionLocal
from app.services.finance.finance_seed_service import (
    STATED_MORTGAGE_HALF_GBP,
    STATED_MORTGAGE_NAME,
    STATED_MORTGAGE_NOTES,
    STATED_PENSION_GBP,
    apply_stated_mortgage_half,
    apply_stated_pension,
    ensure_stated_mortgage_half,
    ensure_stated_pension,
    is_live_finance_database,
)


def test_live_db_check_ignores_test_and_e2e_files() -> None:
    assert is_live_finance_database("sqlite+aiosqlite:///./data/robs_solar.db") is True
    assert is_live_finance_database("sqlite+aiosqlite:////data/robs_solar.db") is True
    assert is_live_finance_database("sqlite+aiosqlite:////tmp/robs_solar.db") is True
    assert is_live_finance_database("sqlite+aiosqlite:///./data/test_robs_solar.db") is False
    assert is_live_finance_database("sqlite+aiosqlite:///./data/e2e_robs_solar.db") is False


@pytest.mark.asyncio
async def test_ensure_stated_pension_skips_test_database() -> None:
    assert await ensure_stated_pension() is None


@pytest.mark.asyncio
async def test_ensure_stated_mortgage_half_skips_test_database() -> None:
    assert await ensure_stated_mortgage_half() is None


@pytest.mark.asyncio
async def test_apply_stated_pension_creates_and_updates() -> None:
    async with SessionLocal() as db:
        created = await apply_stated_pension(db)
        assert created.scope == "personal"
        assert created.account_type == "pension"
        assert created.name == "Pension"
        assert created.balance_gbp == STATED_PENSION_GBP
        account_id = created.id

        updated = await apply_stated_pension(db, amount_gbp=STATED_PENSION_GBP)
        assert updated.id == account_id
        assert updated.balance_gbp == STATED_PENSION_GBP

        rows = list(
            (
                await db.scalars(
                    select(FinanceAccountRow).where(
                        FinanceAccountRow.account_type == "pension",
                        FinanceAccountRow.name == "Pension",
                    )
                )
            ).all()
        )
        assert len(rows) == 1
        created.name = "Workplace pension"
        db.add(created)
        await db.commit()
        kept = await apply_stated_pension(db)
        assert kept.id == account_id
        assert kept.name == "Workplace pension"
        assert kept.balance_gbp == STATED_PENSION_GBP

        leftover = list(
            (
                await db.scalars(
                    select(FinanceAccountRow).where(FinanceAccountRow.account_type == "pension")
                )
            ).all()
        )
        for row in leftover:
            await db.delete(row)
        flag = await db.get(AppSettingRow, "finance.stated_pension_gbp")
        if flag is not None:
            await db.delete(flag)
        await db.commit()


@pytest.mark.asyncio
async def test_apply_stated_mortgage_half_replaces_placeholder() -> None:
    async with SessionLocal() as db:
        created = await apply_stated_mortgage_half(db)
        assert created.scope == "personal"
        assert created.debt_type == "mortgage"
        assert created.name == STATED_MORTGAGE_NAME
        assert created.balance_gbp == STATED_MORTGAGE_HALF_GBP
        assert created.notes == STATED_MORTGAGE_NOTES
        liability_id = created.id

        created.name = "House mortgage (placeholder)"
        created.balance_gbp = 175000.0
        created.notes = "Placeholder £175,000 for now."
        db.add(created)
        await db.commit()

        updated = await apply_stated_mortgage_half(db)
        assert updated.id == liability_id
        assert updated.balance_gbp == STATED_MORTGAGE_HALF_GBP
        assert updated.name == STATED_MORTGAGE_NAME
        assert updated.notes == STATED_MORTGAGE_NOTES
        assert STATED_MORTGAGE_HALF_GBP == round(164421 / 2, 2)

        leftover = list(
            (
                await db.scalars(
                    select(FinanceLiabilityRow).where(FinanceLiabilityRow.debt_type == "mortgage")
                )
            ).all()
        )
        for row in leftover:
            await db.delete(row)
        flag = await db.get(AppSettingRow, "finance.stated_mortgage_half_gbp")
        if flag is not None:
            await db.delete(flag)
        await db.commit()
