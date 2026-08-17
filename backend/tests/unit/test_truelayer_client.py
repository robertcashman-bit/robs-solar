"""TrueLayer client tests."""

import pytest

from app.integrations.truelayer_client import TrueLayerClient
from app.integrations.truelayer_provider import TrueLayerProvider
from app.schemas.finance import TrueLayerConfig


def test_build_authorize_url() -> None:
    client = TrueLayerClient(
        TrueLayerConfig(
            client_id="test-client",
            client_secret="secret",
            redirect_uri="https://app.example.com/callback",
            environment="sandbox",
        )
    )
    url = client.build_authorize_url(state="abc123")
    assert "auth.truelayer-sandbox.com" in url
    assert "client_id=test-client" in url
    assert "state=abc123" in url
    assert "transactions" in url
    assert "cards" in url


@pytest.mark.asyncio
async def test_provider_summarises_recent_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = TrueLayerProvider(
        TrueLayerConfig(
            client_id="test-client",
            client_secret="secret",
            redirect_uri="https://app.example.com/callback",
        ),
        access_token="tok",
    )

    async def fake_recent(*, days: int = 90):
        assert days >= 1
        return [
            {"amount": 2750, "transaction_type": "CREDIT"},
            {"amount": 120, "transaction_type": "DEBIT"},
            {"amount": -40, "transaction_type": "DEBIT"},
        ]

    monkeypatch.setattr(provider._client, "fetch_recent_transactions", fake_recent)
    income, spending = await provider.summarise_recent_activity()
    assert income == 2750
    assert spending == 160
