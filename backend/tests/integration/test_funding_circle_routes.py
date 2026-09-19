"""Funding Circle settings and bank-feed sync routes."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete

from app.db.models import FinanceAccountRow, FinanceLiabilityRow
from app.db.session import SessionLocal
from app.services.finance.funding_circle_sync_service import FundingCircleSyncService
from tests.conftest import login


@pytest_asyncio.fixture(autouse=True)
async def reset_funding_circle_records() -> AsyncGenerator[None, None]:
    async with SessionLocal() as db:
        await db.execute(
            delete(FinanceLiabilityRow).where(FinanceLiabilityRow.name == "Funding Circle")
        )
        await db.execute(
            delete(FinanceAccountRow).where(FinanceAccountRow.external_id == "funding-circle")
        )
        await db.commit()
    yield


@pytest.mark.asyncio
async def test_funding_circle_status_default(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/finance/integrations/funding-circle/status")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["outstanding_gbp"] is None


@pytest.mark.asyncio
async def test_funding_circle_save_settings(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]
    save = await client.put(
        "/finance/integrations/funding-circle/settings",
        json={"outstanding_gbp": 8721.5, "apr_pct": 11.9, "minimum_payment_gbp": 412},
        headers={"X-CSRF-Token": csrf},
    )
    assert save.status_code == 200
    body = save.json()
    assert body["outstanding_gbp"] == 8721.5
    assert body["apr_pct"] == 11.9


@pytest.mark.asyncio
async def test_funding_circle_sync_from_drawdown(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]

    async def fake_load(self, db):  # noqa: ANN001
        return [
            {
                "description": "FUNDING CIRCLE",
                "amount": 10000,
                "transaction_type": "CREDIT",
                "timestamp": "2026-01-15",
            },
            {
                "description": "Funding Circle",
                "amount": -450,
                "transaction_type": "DEBIT",
                "timestamp": "2026-02-15",
            },
        ]

    monkeypatch.setattr(FundingCircleSyncService, "_load_bank_transactions", fake_load)
    result = await client.post(
        "/finance/integrations/funding-circle/sync",
        headers={"X-CSRF-Token": csrf},
    )
    assert result.status_code == 200
    body = result.json()
    assert body["imported"] is True
    assert body["balance_gbp"] == 9550
    assert body["source"] == "bank_feed"

    accounts = (await client.get("/finance/accounts?scope=business")).json()
    assert any(item["name"] == "Funding Circle" for item in accounts)
    debts = (await client.get("/finance/liabilities")).json()
    match = next(item for item in debts if item["name"] == "Funding Circle")
    assert match["balance_gbp"] == 9550
    assert match["account_id"]


@pytest.mark.asyncio
async def test_funding_circle_repayments_only_need_outstanding(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]

    async def fake_load(self, db):  # noqa: ANN001
        return [
            {
                "description": "Funding Circle",
                "amount": -450,
                "transaction_type": "DEBIT",
                "timestamp": "2026-02-15",
            }
        ]

    monkeypatch.setattr(FundingCircleSyncService, "_load_bank_transactions", fake_load)
    result = await client.post(
        "/finance/integrations/funding-circle/sync",
        headers={"X-CSRF-Token": csrf},
    )
    assert result.status_code == 200
    body = result.json()
    assert body["source"] == "needs_outstanding"
    assert body["balance_gbp"] == 0
    debts = (await client.get("/finance/liabilities")).json()
    assert not any(item["name"] == "Funding Circle" for item in debts)

    save = await client.put(
        "/finance/integrations/funding-circle/settings",
        json={"outstanding_gbp": 8000},
        headers={"X-CSRF-Token": csrf},
    )
    assert save.status_code == 200

    second = await client.post(
        "/finance/integrations/funding-circle/sync",
        headers={"X-CSRF-Token": csrf},
    )
    assert second.status_code == 200
    seeded = second.json()
    assert seeded["balance_gbp"] == 8000
    debts = (await client.get("/finance/liabilities")).json()
    assert any(item["name"] == "Funding Circle" and item["balance_gbp"] == 8000 for item in debts)


@pytest.mark.asyncio
async def test_open_banking_routes_removed(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    for path in (
        "/finance/integrations/open-banking/status",
        "/finance/integrations/open-banking/authorize",
    ):
        response = await client.get(path)
        assert response.status_code == 404
