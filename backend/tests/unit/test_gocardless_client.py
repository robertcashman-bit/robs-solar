"""Unit tests for GoCardless Open Banking client helpers."""

import httpx
import pytest

from app.integrations.gocardless_client import (
    GoCardlessClient,
    _pick_balance_amount,
    map_cash_account_type,
)
from app.schemas.finance import OpenBankingConfig


def test_map_cash_account_type() -> None:
    assert map_cash_account_type("CACC", "Current") == "current"
    assert map_cash_account_type("CARD", "Credit card") == "credit_card"
    assert map_cash_account_type(None, "Personal loan") == "loan"


def test_pick_balance_amount_prefers_interim_available() -> None:
    balances = [
        {"balanceType": "closingBooked", "balanceAmount": {"amount": "10.00"}},
        {"balanceType": "interimAvailable", "balanceAmount": {"amount": "25.50"}},
    ]
    assert _pick_balance_amount(balances) == 25.5


@pytest.mark.asyncio
async def test_generate_token_and_list_institutions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token/new/"):
            return httpx.Response(
                200,
                json={
                    "access": "access-token",
                    "refresh": "refresh-token",
                    "access_expires": 3600,
                },
            )
        if request.url.path.endswith("/institutions/"):
            assert request.headers.get("Authorization") == "Bearer access-token"
            return httpx.Response(
                200,
                json=[
                    {"id": "LLOYDS_GB", "name": "Lloyds Bank"},
                    {"id": "VIRGIN_GB", "name": "Virgin Money"},
                ],
            )
        return httpx.Response(404, json={"detail": "not found"})

    client = GoCardlessClient(
        OpenBankingConfig(secret_id="sid", secret_key="skey"),
    )
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:

        async def patched_request(method, path, *, json=None, params=None, auth=True):  # noqa: ANN001
            headers = {"accept": "application/json"}
            if auth:
                token = await client._ensure_access_token()
                headers["Authorization"] = f"Bearer {token}"
            url = f"https://bankaccountdata.gocardless.com/api/v2{path}"
            response = await http_client.request(method, url, headers=headers, json=json, params=params)
            if response.status_code >= 400:
                from app.integrations.gocardless_client import GoCardlessError

                raise GoCardlessError(response.text)
            return response.json()

        client._request = patched_request  # type: ignore[method-assign]

        async def patched_get_json(path: str, *, params=None, auth=True):  # noqa: ANN001
            headers = {"accept": "application/json"}
            if auth:
                token = await client._ensure_access_token()
                headers["Authorization"] = f"Bearer {token}"
            url = f"https://bankaccountdata.gocardless.com/api/v2{path}"
            response = await http_client.get(url, headers=headers, params=params)
            if response.status_code >= 400:
                from app.integrations.gocardless_client import GoCardlessError

                raise GoCardlessError(response.text)
            return response.json()

        client._get_json = patched_get_json  # type: ignore[method-assign]
        institutions = await client.list_institutions(country="gb")

    assert len(institutions) == 2
    assert institutions[0]["name"] == "Lloyds Bank"
