"""Tests for stated personal finance seeds."""

import pytest
from sqlalchemy import select

from app.db.models import AppSettingRow, FinanceAccountRow
from app.db.session import SessionLocal
from app.services.finance.finance_seed_service import (
    STATED_PENSION_GBP,
    apply_stated_pension,
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
