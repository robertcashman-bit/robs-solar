"""Unit tests for Lunch Flow Open Banking client/provider."""

import httpx
import pytest

from app.integrations.lunchflow_client import LunchFlowClient, LunchFlowError
from app.integrations.lunchflow_provider import LunchFlowProvider
from app.schemas.finance import LunchFlowConfig


@pytest.mark.asyncio
async def test_fetch_accounts_and_balances(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LunchFlowClient(LunchFlowConfig(api_key="lf_test_key"))

    async def fake_get(path: str):
        if path == "/accounts":
            return {
                "accounts": [
                    {"id": "acc-1", "name": "Greenacre Current", "institutionName": "Starling"}
                ],
                "total": 1,
            }
        if path.endswith("/balance"):
            return {"balance": {"amount": 1234.56, "currency": "GBP"}}
        raise AssertionError(path)

    monkeypatch.setattr(client, "_get", fake_get)
    accounts = await client.fetch_accounts()
    assert accounts[0]["id"] == "acc-1"
    assert await client.fetch_balance("acc-1") == pytest.approx(1234.56)


@pytest.mark.asyncio
async def test_fetch_transactions_returns_list(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LunchFlowClient(LunchFlowConfig(api_key="lf_test_key"))

    async def fake_get(path: str, params=None):
        if path == "/accounts/acc-1/transactions":
            return {
                "transactions": [
                    {"amount": 2000, "type": "credit", "date": "2026-08-01"},
                    {"amount": 80, "type": "debit", "date": "2026-08-02"},
                ]
            }
        raise AssertionError(path)

    monkeypatch.setattr(client, "_get", fake_get)
    rows = await client.fetch_transactions("acc-1", since="2026-07-14")
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_provider_sync_accounts(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = LunchFlowProvider(LunchFlowConfig(api_key="lf_test_key"))

    async def fake_accounts():
        return [{"id": "acc-1", "name": "Current", "institutionName": "Monzo", "type": "current"}]

    async def fake_balance(_account_id: str) -> float:
        return 99.0

    monkeypatch.setattr(provider._client, "fetch_accounts", fake_accounts)
    monkeypatch.setattr(provider._client, "fetch_balance", fake_balance)
    rows = await provider.sync_accounts()
    assert len(rows) == 1
    assert rows[0]["external_id"] == "acc-1"
    assert rows[0]["balance_gbp"] == pytest.approx(99.0)
    assert rows[0]["name"] == "Monzo — Current"
    assert "Lunch Flow" in rows[0]["notes"]


@pytest.mark.asyncio
async def test_provider_summarises_recent_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime, timezone

    provider = LunchFlowProvider(LunchFlowConfig(api_key="lf_test_key"))
    today = datetime.now(timezone.utc).date().isoformat()

    async def fake_accounts():
        return [{"id": "acc-1", "name": "Current"}]

    async def fake_transactions(_account_id: str, since=None):
        return [
            {"amount": 3000, "type": "credit", "date": today},
            {"amount": 120, "type": "debit", "date": today},
        ]

    monkeypatch.setattr(provider._client, "fetch_accounts", fake_accounts)
    monkeypatch.setattr(provider._client, "fetch_transactions", fake_transactions)
    income, spending = await provider.summarise_recent_activity()
    assert income == 3000
    assert spending == 120


@pytest.mark.asyncio
async def test_invalid_key_maps_to_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LunchFlowClient(LunchFlowConfig(api_key="bad"))

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Forbidden", "message": "Invalid API key."})

    async def fake_get(path: str):
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://www.lunchflow.app/api/v1"
        ) as c:
            response = await c.get(path, headers=client._headers())
        if response.status_code in (401, 403):
            raise LunchFlowError("Lunch Flow rejected the API key.")
        return response.json()

    monkeypatch.setattr(client, "_get", fake_get)
    with pytest.raises(LunchFlowError, match="rejected"):
        await client.fetch_accounts()
