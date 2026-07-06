"""Unit tests for Enable Banking client."""

from datetime import datetime, timezone

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.integrations.enable_banking_client import (
    EnableBankingClient,
    EnableBankingError,
    _pick_enable_balance,
    encode_institution_id,
    parse_institution_id,
)
from app.schemas.finance import OpenBankingConfig


def _test_private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def test_parse_institution_id() -> None:
    assert parse_institution_id("GB:Lloyds Bank") == ("GB", "Lloyds Bank")
    assert parse_institution_id("LLOYDS_GB") == ("GB", "LLOYDS_GB")


def test_encode_institution_id() -> None:
    assert encode_institution_id("gb", "Virgin Money") == "GB:Virgin Money"


def test_pick_enable_balance_prefers_clav() -> None:
    balances = [
        {"balance_type": "BOOK", "balance_amount": {"amount": "10.00", "currency": "GBP"}},
        {"balance_type": "CLAV", "balance_amount": {"amount": "25.50", "currency": "GBP"}},
    ]
    assert _pick_enable_balance(balances) == 25.5


def test_build_jwt_requires_credentials() -> None:
    client = EnableBankingClient(OpenBankingConfig())
    with pytest.raises(EnableBankingError):
        client._build_jwt()


def test_build_jwt_has_kid_header() -> None:
    pem = _test_private_key_pem()
    client = EnableBankingClient(
        OpenBankingConfig(application_id="app-123", private_key_pem=pem),
    )
    token = client._build_jwt()
    assert isinstance(token, str)
    assert token.count(".") == 2


@pytest.mark.asyncio
async def test_list_aspsps_authorize_and_transactions() -> None:
    pem = _test_private_key_pem()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization", "").startswith("Bearer ")
        if request.url.path.endswith("/aspsps"):
            return httpx.Response(
                200,
                json={
                    "aspsps": [
                        {"name": "Lloyds Bank", "country": "GB", "logo": ""},
                        {"name": "Mock ASPSP", "country": "GB", "logo": ""},
                    ]
                },
            )
        if request.url.path.endswith("/sessions"):
            return httpx.Response(
                200,
                json={
                    "session_id": "sess-1",
                    "accounts": [{"uid": "acc-1", "name": "Current", "cash_account_type": "CACC"}],
                },
            )
        if request.url.path.endswith("/accounts/acc-1/balances"):
            return httpx.Response(
                200,
                json={
                    "balances": [
                        {
                            "balance_type": "CLAV",
                            "balance_amount": {"amount": "100.00", "currency": "GBP"},
                        }
                    ]
                },
            )
        if request.url.path.endswith("/accounts/acc-1/transactions"):
            return httpx.Response(
                200,
                json={
                    "transactions": [
                        {
                            "entry_reference": "tx-1",
                            "booking_date": "2026-01-15",
                            "credit_debit_indicator": "DBIT",
                            "status": "BOOK",
                            "transaction_amount": {"amount": "12.50", "currency": "GBP"},
                            "remittance_information": ["Coffee shop"],
                            "creditor": {"name": "Cafe Ltd"},
                        }
                    ]
                },
            )
        return httpx.Response(404, json={"message": "not found"})

    client = EnableBankingClient(
        OpenBankingConfig(application_id="app-123", private_key_pem=pem),
    )

    async def patched_request(method, path, *, json=None, params=None):
        token = client._build_jwt()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if json is not None:
            headers["Content-Type"] = "application/json"
        url = f"https://api.enablebanking.com{path}"
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            response = await http_client.request(method, url, headers=headers, json=json, params=params)
        if response.status_code >= 400:
            raise EnableBankingError(response.text)
        return response.json()

    client._request = patched_request  # type: ignore[method-assign]

    rows = await client.list_aspsps(country="GB", query="Lloyds")
    assert len(rows) == 1
    assert rows[0]["name"] == "Lloyds Bank"

    session = await client.authorize_session(code="auth-code")
    assert session["session_id"] == "sess-1"

    record = await client.fetch_account_record(
        account={"uid": "acc-1", "name": "Current", "cash_account_type": "CACC"},
        institution_name="Lloyds Bank",
    )
    assert record is not None
    assert record["balance_gbp"] == 100.0
    assert record["external_id"] == "openbanking:enable:acc-1"

    transactions = await client.get_account_transactions("acc-1", date_from="2026-01-01")
    assert len(transactions) == 1
    assert transactions[0]["entry_reference"] == "tx-1"
