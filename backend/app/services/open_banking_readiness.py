"""Cached Open Banking provider readiness probe."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.open_banking_provider import OpenBankingProvider
from app.schemas.finance import OpenBankingConfig, OpenBankingTestStatus
from app.services.open_banking_setup_validation import classify_test_error

_TTL_SECONDS = 60


@dataclass(frozen=True)
class ReadinessSnapshot:
    provider_ready: bool
    readiness_message: str | None
    readiness_status: OpenBankingTestStatus


_CACHE: dict[str, tuple[float, ReadinessSnapshot]] = {}


def _cache_key(config: OpenBankingConfig) -> str:
    return (
        f"{config.provider}:{config.application_id}:{config.secret_id}:"
        f"{config.environment}:{config.country}"
    )


async def probe_provider_readiness(config: OpenBankingConfig) -> ReadinessSnapshot:
    """Verify the provider can list institutions (requires an active Enable Banking app)."""
    key = _cache_key(config)
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _TTL_SECONDS:
        return cached[1]

    provider = OpenBankingProvider(config)
    try:
        await provider.list_institutions(country=config.country, query="")
        snapshot = ReadinessSnapshot(
            provider_ready=True,
            readiness_message=None,
            readiness_status="connected_successfully",
        )
    except (IntegrationNotConfiguredError, Exception) as exc:
        classified = classify_test_error(exc)
        snapshot = ReadinessSnapshot(
            provider_ready=False,
            readiness_message=classified.message,
            readiness_status=classified.status,
        )

    _CACHE[key] = (now, snapshot)
    return snapshot
