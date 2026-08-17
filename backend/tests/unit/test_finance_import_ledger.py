"""Import pipeline: validate, preview, commit, duplicates, rollback."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow, FinanceTransactionRow
from app.db.session import SessionLocal
from app.services.finance.finance_import_service import finance_import_service
from app.services.finance.money import from_pence, to_pence


def _row(**overrides):
    base = {
        "posted_on": "2026-07-01",
        "amount_gbp": -12.34,
        "description": "TESCO",
        "account_name": "Current",
        "account_external_id": "acc-1",
        "external_id": "tx-1",
        "scope": "personal",
        "currency": "GBP",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_validate_rejects_malformed_zero_and_future() -> None:
    service = finance_import_service
    assert service.validate_row({"amount_gbp": 10}, source="manual")[0] is None
    assert service.validate_row(_row(amount_gbp=0), source="manual")[1] == "Zero amount"
    assert service.validate_row(_row(posted_on="not-a-date"), source="manual")[0] is None
    assert service.validate_row(_row(posted_on="2099-01-01"), source="manual")[1] == "Future date"
    assert service.validate_row(_row(currency="USD"), source="manual")[0] is None
    missing_account = _row(account_external_id="", account_name="")
    assert service.validate_row(missing_account, source="manual")[0] is None
    valid, reason = service.validate_row(_row(amount_gbp=-1_000_000.55), source="manual")
    assert reason == ""
    assert valid is not None
    assert valid["amount_pence"] == -100000055


@pytest.mark.asyncio
async def test_preview_does_not_write(setup_db: None) -> None:
    async with SessionLocal() as db:
        from sqlalchemy import select

        preview = await finance_import_service.preview(db, [_row()], source="lunchflow")
        assert preview["new_count"] == 1
        assert preview["rejected_count"] == 0
        stored = (await db.scalars(select(FinanceTransactionRow))).all()
        assert stored == []
        assert preview["money_out_gbp"] == 12.34


@pytest.mark.asyncio
async def test_commit_persists_and_flags_duplicates(setup_db: None) -> None:
    async with SessionLocal() as db:
        first = await finance_import_service.commit(db, [_row()], source="lunchflow")
        assert first["imported"] == 1
        second = await finance_import_service.commit(db, [_row()], source="lunchflow")
        assert second["imported"] == 0
        assert second["duplicate_count"] == 1
        from sqlalchemy import select

        rows = (await db.scalars(select(FinanceTransactionRow))).all()
        assert len(rows) == 1
        assert rows[0].amount_pence == -1234
        assert rows[0].category == ""


@pytest.mark.asyncio
async def test_negative_refund_and_transfer(setup_db: None) -> None:
    rows = [
        _row(external_id="in-1", amount_gbp=2500.00, description="PAY"),
        _row(external_id="out-1", amount_gbp=-40.10, description="SHOP"),
        _row(external_id="tr-1", amount_gbp=-100, description="TO SAVINGS", type="transfer"),
    ]
    async with SessionLocal() as db:
        result = await finance_import_service.commit(db, rows, source="manual")
        assert result["imported"] == 3
        assert result["money_in_gbp"] == 2500
        assert result["money_out_gbp"] == 140.1


@pytest.mark.asyncio
async def test_interrupted_import_rolls_back(
    setup_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_flush = AsyncSession.flush

    async def boom(self, *args, **kwargs):
        await original_flush(self, *args, **kwargs)
        raise RuntimeError("interrupted")

    monkeypatch.setattr(AsyncSession, "flush", boom)
    async with SessionLocal() as db:
        with pytest.raises(RuntimeError, match="interrupted"):
            await finance_import_service.commit(db, [_row()], source="lunchflow")
    async with SessionLocal() as db:
        from sqlalchemy import select

        assert (await db.scalars(select(FinanceTransactionRow))).all() == []


@pytest.mark.asyncio
async def test_persistence_across_sessions(setup_db: None) -> None:
    async with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        db.add(
            FinanceAccountRow(
                scope="personal",
                account_type="current",
                name="Current",
                provider="Test",
                balance_gbp=10,
                notes="",
                source="manual",
                external_id="acc-1",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        await db.commit()
        await finance_import_service.commit(db, [_row()], source="lunchflow")
    async with SessionLocal() as db:
        from sqlalchemy import select

        rows = (await db.scalars(select(FinanceTransactionRow))).all()
        assert len(rows) == 1
        assert from_pence(rows[0].amount_pence) == -12.34
        assert rows[0].account_name == "Current"


def test_penny_helpers() -> None:
    assert to_pence("10.105") == 1010
    assert to_pence(-0.1) == -10
    assert from_pence(1) == 0.01
    assert from_pence(-199) == -1.99
