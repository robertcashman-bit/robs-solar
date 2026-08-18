"""P&L compare uses stored transactions with signed deltas."""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.db.models import FinanceTransactionRow
from app.db.session import SessionLocal
from tests.conftest import login


def _txn(**kwargs: object) -> FinanceTransactionRow:
    now = datetime.now(timezone.utc)
    amount = int(kwargs["amount_pence"])  # type: ignore[arg-type]
    posted = str(kwargs["posted_on"])
    return FinanceTransactionRow(
        scope=str(kwargs.get("scope", "personal")),
        account_id=None,
        account_name=str(kwargs.get("account_name", "Current")),
        external_id=None,
        posted_on=posted,
        amount_pence=amount,
        description=str(kwargs.get("description", "TX")),
        txn_type="expense" if amount < 0 else "income",
        category=str(kwargs.get("category", "General")),
        source="manual",
        fingerprint=str(kwargs.get("fingerprint", f"{posted}:{amount}:{kwargs.get('scope')}")),
        is_transfer=False,
        is_deleted=False,
        excluded_from_budget=False,
        currency="GBP",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_pnl_compare_last_month_vs_prior(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.finance import finance_period as period_mod

    class _DT:
        timezone = timezone

        @staticmethod
        def now(tz=None):
            return datetime(2026, 8, 18, tzinfo=timezone.utc)

    monkeypatch.setattr(period_mod, "datetime", _DT)
    async with SessionLocal() as db:
        await db.execute(delete(FinanceTransactionRow))
        db.add_all(
            [
                _txn(posted_on="2026-07-10", amount_pence=500_000, description="July income"),
                _txn(posted_on="2026-07-12", amount_pence=-100_000, description="July spend"),
                _txn(posted_on="2026-06-10", amount_pence=400_000, description="June income"),
                _txn(posted_on="2026-06-12", amount_pence=-50_000, description="June spend"),
            ]
        )
        await db.commit()

    await login(client, "viewer", "viewer-pass")
    body = (await client.get("/finance/pnl-compare?scope=personal")).json()
    assert body["scope"] == "personal"
    assert len(body["rows"]) == 4
    last_month = next(row for row in body["rows"] if row["key"] == "1m")
    assert last_month["income_gbp"] == 5000.0
    assert last_month["spending_gbp"] == 1000.0
    assert last_month["surplus_gbp"] == 4000.0
    assert last_month["compare_income_gbp"] == 4000.0
    assert last_month["income_change_gbp"] == 1000.0
    smly = next(row for row in body["rows"] if row["key"] == "smly")
    assert smly["compare_empty"] is True
    assert smly["income_change_gbp"] is None
