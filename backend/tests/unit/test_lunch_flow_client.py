"""Unit tests for Lunch Flow API client."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations.lunch_flow_client import LunchFlowClient, LunchFlowError
from app.schemas.finance import LunchFlowConfig


@pytest.mark.asyncio
@respx.mock
async def test_test_connection_zero_accounts_includes_hint() -> None:
    respx.get("https://www.lunchflow.app/api/v1/accounts").mock(
        return_value=httpx.Response(200, json={"accounts": []})
    )
    client = LunchFlowClient(LunchFlowConfig(api_key="test-key"))
    result = await client.test_connection()
    assert result["accounts"] == 0
    assert "Account Access" in str(result.get("hint") or "")


@pytest.mark.asyncio
@respx.mock
async def test_list_accounts_success() -> None:
    respx.get("https://www.lunchflow.app/api/v1/accounts").mock(
        return_value=httpx.Response(
            200,
            json={
                "accounts": [
                    {
                        "id": 1,
                        "name": "Current",
                        "institution_name": "Lloyds Bank",
                        "institution_logo": "",
                        "provider": "gocardless",
                        "status": "ACTIVE",
                    }
                ]
            },
        )
    )
    client = LunchFlowClient(LunchFlowConfig(api_key="test-key"))
    rows = await client.list_accounts()
    assert len(rows) == 1
    assert rows[0]["institution_name"] == "Lloyds Bank"


@pytest.mark.asyncio
@respx.mock
async def test_test_connection_invalid_key() -> None:
    respx.get("https://www.lunchflow.app/api/v1/accounts").mock(
        return_value=httpx.Response(
            401, json={"error": "Unauthorized", "message": "Invalid API key"}
        )
    )
    client = LunchFlowClient(LunchFlowConfig(api_key="bad"))
    with pytest.raises(LunchFlowError, match="Invalid Lunch Flow API key"):
        await client.test_connection()


@pytest.mark.asyncio
@respx.mock
async def test_test_connection_forbidden_surfaces_api_message() -> None:
    # Live API returns 403 "Invalid credentials." for a bad key.
    respx.get("https://www.lunchflow.app/api/v1/accounts").mock(
        return_value=httpx.Response(
            403, json={"error": "Forbidden", "message": "Invalid credentials."}
        )
    )
    client = LunchFlowClient(LunchFlowConfig(api_key="bad"))
    with pytest.raises(LunchFlowError, match="Invalid credentials"):
        await client.test_connection()


@pytest.mark.asyncio
@respx.mock
async def test_get_account_balance_and_transactions() -> None:
    respx.get("https://www.lunchflow.app/api/v1/accounts/7/balance").mock(
        return_value=httpx.Response(
            200,
            json={"balance": {"available": 1200.0, "current": 1250.0, "currency": "GBP"}},
        )
    )
    respx.get("https://www.lunchflow.app/api/v1/accounts/7/transactions").mock(
        return_value=httpx.Response(
            200,
            json={
                "transactions": [
                    {
                        "id": "tx-1",
                        "account_id": 7,
                        "date": "2026-07-01",
                        "amount": -42.5,
                        "currency": "GBP",
                        "description": "Coffee shop",
                        "merchant_name": "Cafe",
                    }
                ]
            },
        )
    )
    client = LunchFlowClient(LunchFlowConfig(api_key="test-key"))
    balance = await client.get_account_balance(7)
    assert balance["current"] == 1250.0
    transactions = await client.get_account_transactions(7)
    assert transactions[0]["description"] == "Coffee shop"
