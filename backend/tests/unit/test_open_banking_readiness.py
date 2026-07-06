"""Unit tests for Open Banking readiness probe."""

import pytest

from app.integrations.base import IntegrationNotConfiguredError
from app.schemas.finance import OpenBankingConfig
from app.services import open_banking_readiness as readiness_module
from app.services.open_banking_readiness import probe_provider_readiness


@pytest.mark.asyncio
async def test_probe_provider_readiness_inactive_app(monkeypatch: pytest.MonkeyPatch) -> None:
    readiness_module._CACHE.clear()

    class FakeProvider:
        async def list_institutions(self, *, country: str, query: str) -> list[dict[str, str]]:
            raise IntegrationNotConfiguredError("Enable Banking 403: Application is not active")

    monkeypatch.setattr(
        readiness_module,
        "OpenBankingProvider",
        lambda _config: FakeProvider(),
    )

    config = OpenBankingConfig(
        provider="enable_banking",
        application_id="app-123",
        private_key_pem="-----BEGIN RSA PRIVATE KEY-----\nabc",
        country="gb",
    )
    snapshot = await probe_provider_readiness(config)
    assert snapshot.provider_ready is False
    assert snapshot.readiness_status == "further_bank_authorisation_required"
    assert snapshot.readiness_message is not None


@pytest.mark.asyncio
async def test_probe_provider_readiness_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    readiness_module._CACHE.clear()
    calls = {"count": 0}

    class FakeProvider:
        async def list_institutions(self, *, country: str, query: str) -> list[dict[str, str]]:
            calls["count"] += 1
            return [{"id": "GB:Lloyds Bank", "name": "Lloyds Bank", "logo": ""}]

    monkeypatch.setattr(
        readiness_module,
        "OpenBankingProvider",
        lambda _config: FakeProvider(),
    )

    config = OpenBankingConfig(
        provider="enable_banking",
        application_id="app-cache",
        private_key_pem="-----BEGIN RSA PRIVATE KEY-----\nabc",
        country="gb",
    )
    first = await probe_provider_readiness(config)
    second = await probe_provider_readiness(config)
    assert first.provider_ready is True
    assert second.provider_ready is True
    assert calls["count"] == 1
