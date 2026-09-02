"""History budget math: windows, renormalize, annual provision, insufficient data."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from app.db.models import FinanceTransactionRow
from app.db.session import SessionLocal
from app.services.finance.finance_health_service import finance_health_service
from app.services.finance.finance_sinking_fund_service import _contribution
from app.services.finance.history_budget_service import (
    _add_months,
    _month_start,
    history_budget_service,
)


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
        is_transfer=kwargs.get("is_transfer", False),
        is_deleted=False,
        currency="GBP",
        created_at=now,
        updated_at=now,
    )


def _month_iso(today: date, months_ago: int, day: int = 15) -> str:
    start = _add_months(_month_start(today), -months_ago)
    return start.replace(day=min(day, 28)).isoformat()


def _freeze_history_today(monkeypatch: pytest.MonkeyPatch, today: date) -> date:
    """Pin history budget 'today' so early-month runs do not scale MTD windows."""
    from app.services.finance import history_budget_service as hist_mod

    class _DT:
        timezone = timezone

        @staticmethod
        def now(tz=None):
            return datetime(today.year, today.month, today.day, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(hist_mod, "datetime", _DT)
    return today


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
async def test_36_month_window_used_from_stored_totals_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full 36 months of steady spend → 36m window participates; amount from txs only."""
    today = _freeze_history_today(monkeypatch, date(2026, 8, 18))
    async with SessionLocal() as db:
        for months_ago in range(36):
            db.add(
                _tx(
                    posted_on=_month_iso(today, months_ago),
                    amount_pence=-3000,
                    fingerprint=f"food-36-{months_ago}",
                    category="Food",
                )
            )
            db.add(
                _tx(
                    posted_on=_month_iso(today, months_ago, day=5),
                    amount_pence=200000,
                    fingerprint=f"income-36-{months_ago}",
                    category="Salary",
                    description="PAY",
                )
            )
        await db.commit()
        preview = await history_budget_service.preview(db, "personal")
        food = next(item for item in preview["lines"] if item["category"] == "Food")
        assert food["insufficient_data"] is False
        assert food["amount_gbp"] == 30.0
        basis = json.loads(food["basis_json"])
        assert "36" in basis.get("windows", {}) or "36" in basis.get("weights", {})
        assert food["confidence"] in {"High", "Medium"}
        # Income also blends stored totals only (£2000/mo).
        assert preview["income"]["insufficient_data"] is False
        assert preview["income"]["amount_gbp"] == 2000.0
        income_basis = json.loads(preview["income"]["basis_json"])
        assert "36" in income_basis.get("windows", {}) or "36" in income_basis.get(
            "weights", {}
        )
        assert "36" in preview["explanation"]


@pytest.mark.asyncio
async def test_24_month_history_still_enables_36_month_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """24 months of QuickFile-style history qualifies the 36m window (coverage=24)."""
    today = _freeze_history_today(monkeypatch, date(2026, 8, 18))
    async with SessionLocal() as db:
        for months_ago in range(24):
            db.add(
                _tx(
                    posted_on=_month_iso(today, months_ago),
                    amount_pence=-5000,
                    fingerprint=f"food-24-{months_ago}",
                    category="Food",
                )
            )
        await db.commit()
        preview = await history_budget_service.preview(db, "personal")
        food = next(item for item in preview["lines"] if item["category"] == "Food")
        basis = json.loads(food["basis_json"])
        assert "36" in basis.get("windows", {})
        # Amount is derived only from the £50/mo stored rows (no invented figures).
        assert food["amount_gbp"] > 0
        assert food["amount_gbp"] <= 50.0
        assert food["confidence"] in {"High", "Medium"}


@pytest.mark.asyncio
async def test_short_history_falls_back_to_3_month_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only 3 months (Lunch Flow style) → 36/12 dropped; 3m still returns lines."""
    today = _freeze_history_today(monkeypatch, date(2026, 8, 18))
    async with SessionLocal() as db:
        for months_ago in range(3):
            db.add(
                _tx(
                    posted_on=_month_iso(today, months_ago),
                    amount_pence=-4500,
                    fingerprint=f"food-3-{months_ago}",
                    category="Food",
                )
            )
            db.add(
                _tx(
                    posted_on=_month_iso(today, months_ago, day=3),
                    amount_pence=150000,
                    fingerprint=f"pay-3-{months_ago}",
                    category="Salary",
                    description="PAY",
                )
            )
        await db.commit()
        preview = await history_budget_service.preview(db, "personal")
        assert preview["lines"], "short history must still produce expense lines"
        food = next(item for item in preview["lines"] if item["category"] == "Food")
        assert food["amount_gbp"] == 45.0
        basis = json.loads(food["basis_json"])
        weights = {int(key): value for key, value in basis.get("weights", {}).items()}
        assert 36 not in weights
        assert 12 not in weights
        assert 3 in weights
        assert preview["income"]["amount_gbp"] == 1500.0
        income_basis = json.loads(preview["income"]["basis_json"])
        income_weights = {
            int(key): value for key, value in income_basis.get("weights", {}).items()
        }
        assert 36 not in income_weights
        assert 12 not in income_weights
        assert 3 in income_weights


@pytest.mark.asyncio
async def test_transfers_and_uncategorised_excluded_from_history_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = _freeze_history_today(monkeypatch, date(2026, 8, 18))
    async with SessionLocal() as db:
        for months_ago in range(6):
            db.add(
                _tx(
                    posted_on=_month_iso(today, months_ago),
                    amount_pence=-2000,
                    fingerprint=f"food-ex-{months_ago}",
                    category="Food",
                )
            )
        # Transfer and blank category must not create lines or inflate averages.
        db.add(
            _tx(
                posted_on=_month_iso(today, 0),
                amount_pence=-99999,
                fingerprint="xfer",
                category="Transfers",
                is_transfer=True,
                description="INTERNAL TRANSFER",
            )
        )
        db.add(
            _tx(
                posted_on=_month_iso(today, 0),
                amount_pence=-88888,
                fingerprint="uncat-big",
                category="",
                description="UNKNOWN MERCHANT",
            )
        )
        await db.commit()
        preview = await history_budget_service.preview(db, "personal")
        assert preview["uncategorised_count"] == 1
        categories = {item["category"] for item in preview["lines"]}
        assert "Food" in categories
        assert "Transfers" not in categories
        assert "" not in categories
        food = next(item for item in preview["lines"] if item["category"] == "Food")
        # £20/mo only — transfer and uncategorised amounts must not appear.
        assert food["amount_gbp"] == 20.0
        assert 999.99 not in (food["amount_gbp"],)
        assert "999.99" not in food["basis_json"]
        assert "888.88" not in food["basis_json"]


@pytest.mark.asyncio
async def test_exceptional_one_off_txn_excluded_before_monthly_average(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nine £50 bills + one £9,000 one-off → ~£50/mo, not dragged by £9k."""
    today = _freeze_history_today(monkeypatch, date(2026, 8, 18))
    async with SessionLocal() as db:
        for months_ago in range(9):
            db.add(
                _tx(
                    posted_on=_month_iso(today, months_ago),
                    amount_pence=-5000,
                    fingerprint=f"bill-typical-{months_ago}",
                    category="Home improvements",
                )
            )
        db.add(
            _tx(
                posted_on=_month_iso(today, 1, day=20),
                amount_pence=-900000,
                fingerprint="solar-one-off",
                category="Home improvements",
                description="SOLAR INSTALLATION",
            )
        )
        await db.commit()
        preview = await history_budget_service.preview(db, "personal")
        line = next(item for item in preview["lines"] if item["category"] == "Home improvements")
        assert line["insufficient_data"] is False
        # Typical £50/mo scale — must not be a mean pulled toward £9k.
        assert 40.0 <= line["amount_gbp"] <= 55.0
        basis = json.loads(line["basis_json"])
        assert basis["outlier_txs_excluded"] == 1
        assert basis["txn_count"] == 9
        assert basis["txn_count_before_outliers"] == 10
        assert "excluded 1 exceptional txn" in line["source_note"]
        assert "9000" not in line["source_note"]


@pytest.mark.asyncio
async def test_clean_series_unchanged_when_no_txn_outliers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Steady category with no exceptional txs keeps the same recommendation."""
    today = _freeze_history_today(monkeypatch, date(2026, 8, 18))
    async with SessionLocal() as db:
        for months_ago in range(12):
            db.add(
                _tx(
                    posted_on=_month_iso(today, months_ago),
                    amount_pence=-5000,
                    fingerprint=f"clean-{months_ago}",
                    category="Food",
                )
            )
        await db.commit()
        preview = await history_budget_service.preview(db, "personal")
        food = next(item for item in preview["lines"] if item["category"] == "Food")
        assert food["amount_gbp"] == 50.0
        basis = json.loads(food["basis_json"])
        assert basis.get("outlier_txs_excluded", 0) == 0
        assert "exceptional txn" not in food["source_note"]


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
