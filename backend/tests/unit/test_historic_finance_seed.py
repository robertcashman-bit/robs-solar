"""Tests for historic finance seed and historic flags."""

import pytest
from sqlalchemy import select

from app.db.models import FinanceAccountRow, PersonalFinanceSnapshotRow
from app.db.session import SessionLocal
from app.schemas.finance import FinanceAccountSource, account_is_historic
from app.services.finance.historic_finance_seed import seed_historic_finance


def test_account_is_historic() -> None:
    assert account_is_historic(FinanceAccountSource.MANUAL) is True
    assert account_is_historic(FinanceAccountSource.QUICKFILE) is False
    assert account_is_historic(FinanceAccountSource.OPEN_BANKING) is False


@pytest.mark.asyncio
async def test_seed_historic_finance_idempotent() -> None:
    async with SessionLocal() as db:
        await seed_historic_finance(db)
        second = await seed_historic_finance(db)

        assert second.skipped is True

        lloyds = await db.scalar(
            select(FinanceAccountRow).where(FinanceAccountRow.name == "Lloyds personal")
        )
        assert lloyds is not None
        assert lloyds.balance_gbp == 2500.0
        assert lloyds.source == "manual"

        snapshot = await db.scalar(
            select(PersonalFinanceSnapshotRow).where(
                PersonalFinanceSnapshotRow.monthly_income_gbp == 4000.0
            )
        )
        assert snapshot is not None
