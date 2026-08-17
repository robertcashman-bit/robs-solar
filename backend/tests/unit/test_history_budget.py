"""History budget math: windows, renormalize, annual provision, insufficient data."""

from datetime import datetime, timezone

import pytest

from app.db.models import FinanceTransactionRow
from app.db.session import SessionLocal
from app.services.finance.finance_health_service import finance_health_service
from app.services.finance.finance_sinking_fund_service import _contribution
from app.services.finance.history_budget_service import history_budget_service


def _tx(**kwargs) -> FinanceTransactionRow:
    now = datetime.now(timezone.utc)
    return FinanceTransactionRow(
        scope=kwargs.get("scope", "personal"),
        account_id=None,
        account_name="Current",
        external_id=kwargs.get("external_id"),
        posted_on=kwargs["posted_on"],
        amount_pence=kwargs["amount_pence"],
        description=kwargs.get("description", "SHOP"),
        txn_type="expense" if kwargs["amount_pence"] < 0 else "income",
        category=kwargs.get("category", "Food"),
        source="manual",
        fingerprint=kwargs.get("fingerprint", kwargs["posted_on"] + str(kwargs["amount_pence"])),
        is_transfer=False,
        is_deleted=False,
        currency="GBP",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_weighted_windows_and_insufficient() -> None:
    async with SessionLocal() as db:
        # 12 months of Food at £30, plus a 3-month spike so 3m average differs.
        for month in range(1, 13):
            db.add(
                _tx(
                    posted_on=f"2025-{month:02d}-15",
                    amount_pence=-3000,
                    fingerprint=f"food-{month}",
                )
            )
        for month in (6, 7, 8):
            db.add(
                _tx(
                    posted_on=f"2026-{month:02d}-10",
                    amount_pence=-9000,
                    fingerprint=f"food-spike-{month}",
                    category="Food",
                )
            )
        db.add(
            _tx(
                posted_on="2026-08-01",
                amount_pence=-500,
                category="",
                fingerprint="uncat",
                description="UNKNOWN MERCHANT",
            )
        )
        await db.commit()
        preview = await history_budget_service.preview(db, "personal")
        food = next(item for item in preview["lines"] if item["category"] == "Food")
        assert food["insufficient_data"] is False
        assert food["amount_gbp"] > 0
        basis = food["basis_json"]
        assert "weighted_average" in basis or "annual" in basis or "median" in basis
        assert preview["uncategorised_count"] == 1
        empty = await history_budget_service.preview(db, "business")
        assert empty["lines"] == []
        assert empty["income"]["insufficient_data"] is True


@pytest.mark.asyncio
async def test_annual_bill_divided_by_twelve() -> None:
    async with SessionLocal() as db:
        db.add(
            _tx(
                posted_on="2024-08-01",
                amount_pence=-120000,
                category="Insurance",
                fingerprint="ins-1",
            )
        )
        db.add(
            _tx(
                posted_on="2025-08-03",
                amount_pence=-120000,
                category="Insurance",
                fingerprint="ins-2",
            )
        )
        await db.commit()
        preview = await history_budget_service.preview(db, "personal")
        insurance = next(item for item in preview["lines"] if item["category"] == "Insurance")
        assert insurance["amount_gbp"] == 100.0
        assert "/ 12" in insurance["source_note"] or "/ 12" in insurance["basis_json"]


def test_sinking_fund_formula() -> None:
    math = _contribution(1200, 0, "2027-08-16")
    assert math["months_left"] >= 1
    assert math["monthly_contribution_gbp"] == round(1200 / math["months_left"], 2)
    assert math["formula"].startswith("1200.0 / ")


@pytest.mark.asyncio
async def test_self_heal_rebuilds_cache_without_changing_txs() -> None:
    async with SessionLocal() as db:
        db.add(
            _tx(
                posted_on="2026-08-01",
                amount_pence=-2000,
                category="Food",
                source="lunchflow",
                fingerprint="heal-1",
            )
        )
        await db.commit()
        result = await finance_health_service.self_heal(db)
        assert result["source_transactions_unchanged"] is True
        assert result["transaction_count"] == 1
