"""Period flow totals isolate personal vs business scopes."""

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


async def _seed_txns() -> None:
    async with SessionLocal() as db:
        await db.execute(delete(FinanceTransactionRow))
        db.add_all(
            [
                _txn(
                    scope="personal",
                    posted_on="2026-07-10",
                    description="Salary",
                    amount_pence=300_000,
                    category="Income",
                ),
                _txn(
                    scope="personal",
                    posted_on="2026-07-12",
                    description="Groceries",
                    amount_pence=-40_000,
                    category="Food",
                ),
                _txn(
                    scope="business",
                    posted_on="2026-07-15",
                    description="Client invoice",
                    amount_pence=500_000,
                    category="Sales",
                    account_name="Business",
                ),
                _txn(
                    scope="business",
                    posted_on="2026-07-16",
                    description="Supplies",
                    amount_pence=-50_000,
                    category="Expenses",
                    account_name="Business",
                ),
            ]
        )
        await db.commit()


@pytest.mark.asyncio
async def test_period_flow_scope_isolation(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.finance import finance_period as period_mod

    class _DT:
        timezone = timezone

        @staticmethod
        def now(tz=None):
            return datetime(2026, 8, 18, tzinfo=timezone.utc)

    monkeypatch.setattr(period_mod, "datetime", _DT)
    await _seed_txns()
    await login(client, "viewer", "viewer-pass")

    personal = (await client.get("/finance/period-flow?period=1m&scope=personal")).json()
    business = (await client.get("/finance/period-flow?period=1m&scope=business")).json()

    assert personal["scope"] == "personal"
    assert business["scope"] == "business"
    assert personal["income_gbp"] == 3000.0
    assert personal["spending_gbp"] == 400.0
    assert personal["surplus_gbp"] == 2600.0
    assert business["income_gbp"] == 5000.0
    assert business["spending_gbp"] == 500.0
    assert personal["income_gbp"] != business["income_gbp"]
    assert personal["transaction_count"] == 2
    assert business["transaction_count"] == 2


@pytest.mark.asyncio
async def test_overview_includes_separate_period_flows(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.finance import finance_period as period_mod

    class _DT:
        timezone = timezone

        @staticmethod
        def now(tz=None):
            return datetime(2026, 8, 18, tzinfo=timezone.utc)

    monkeypatch.setattr(period_mod, "datetime", _DT)
    await _seed_txns()
    await login(client, "viewer", "viewer-pass")

    response = await client.get(
        "/finance/overview?personal_period=1m&business_period=3m"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["personal_period_flow"]["period"] == "1m"
    assert body["personal_period_flow"]["scope"] == "personal"
    assert body["personal_period_flow"]["income_gbp"] == 3000.0
    assert body["business_period_flow"]["period"] == "3m"
    assert body["business_period_flow"]["scope"] == "business"
    assert body["business_period_flow"]["income_gbp"] == 5000.0
