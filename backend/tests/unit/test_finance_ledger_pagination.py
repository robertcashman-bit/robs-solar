"""Transaction list filters in SQL and paginates instead of scanning in Python."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


async def _admin(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> str:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    return data["csrf_token"]


@pytest.mark.asyncio
async def test_transaction_filters_and_offset(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    rows = [
        {
            "posted_on": "2026-07-02",
            "amount_gbp": -20.5,
            "description": "NETFLIX",
            "account_name": "Current",
            "account_external_id": "acc-1",
            "external_id": "n-1",
            "scope": "personal",
        },
        {
            "posted_on": "2026-07-03",
            "amount_gbp": 2000,
            "description": "SALARY",
            "account_name": "Current",
            "account_external_id": "acc-1",
            "external_id": "n-2",
            "scope": "personal",
        },
        {
            "posted_on": "2026-07-04",
            "amount_gbp": -12,
            "description": "TESCO",
            "account_name": "Current",
            "account_external_id": "acc-1",
            "external_id": "n-3",
            "scope": "personal",
        },
    ]
    committed = await client.post(
        "/finance/transactions/import/commit",
        json={"source": "manual", "rows": rows},
        headers={"X-CSRF-Token": csrf},
    )
    assert committed.status_code == 200
    assert committed.json()["imported"] == 3

    first = await client.get("/finance/transactions?limit=2&offset=0")
    assert first.status_code == 200
    assert len(first.json()) == 2
    second = await client.get("/finance/transactions?limit=2&offset=2")
    assert len(second.json()) == 1
    ids = {row["id"] for row in first.json() + second.json()}
    assert len(ids) == 3

    income = await client.get("/finance/transactions?filter=income")
    assert [row["description"] for row in income.json()] == ["SALARY"]

    expenses = await client.get("/finance/transactions?filter=expenses")
    assert {row["description"] for row in expenses.json()} == {"NETFLIX", "TESCO"}

    search = await client.get("/finance/transactions?q=tesco")
    assert [row["description"] for row in search.json()] == ["TESCO"]


@pytest.mark.asyncio
async def test_list_transactions_paginates_ten_thousand(setup_db: None) -> None:
    from datetime import datetime, timezone
    from time import perf_counter

    from app.db.models import FinanceTransactionRow
    from app.db.session import SessionLocal
    from app.services.finance.finance_ledger_service import finance_ledger_service

    now = datetime.now(timezone.utc)
    rows = [
        FinanceTransactionRow(
            scope="personal",
            account_name="Current",
            posted_on="2026-08-01",
            amount_pence=-100,
            description=f"TX {index}",
            source="manual",
            fingerprint=f"bulk-{index}",
            created_at=now,
            updated_at=now,
        )
        for index in range(10_000)
    ]
    async with SessionLocal() as db:
        db.add_all(rows)
        await db.commit()
        started = perf_counter()
        page = await finance_ledger_service.list_transactions(db, limit=50, offset=0)
        elapsed = perf_counter() - started
        later = await finance_ledger_service.list_transactions(db, limit=50, offset=9950)
    assert len(page) == 50
    assert len(later) == 50
    assert elapsed < 1.0
