"""Unit tests for fast Connections status / light health paths."""

from __future__ import annotations

import time

import pytest
from httpx import AsyncClient

from app.services.finance.connection_status_service import (
    _env_only_bundle,
    light_integration_flags,
)
from app.services.finance.finance_health_service import finance_health_service
from tests.conftest import login


@pytest.mark.asyncio
async def test_light_health_skips_heavy_lookups(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    started = time.perf_counter()
    response = await client.get("/finance/health?light=1")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body.get("light") is True
    assert "quickfile" in body["integrations"]
    assert "lunchflow" in body["integrations"]
    assert "truelayer" not in body.get("integrations", {})
    # Local ASGI should be well under a second; keep a soft ceiling for CI.
    assert elapsed_ms < 2000, f"light health too slow: {elapsed_ms:.1f}ms"


@pytest.mark.asyncio
async def test_connection_status_bundle_is_fast(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    started = time.perf_counter()
    response = await client.get("/finance/integrations/connection-status")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert response.status_code == 200
    body = response.json()
    assert "lunchflow" in body
    assert "quickfile" in body
    assert "funding_circle" in body
    assert body["lunchflow"]["provider"] == "lunchflow"
    assert elapsed_ms < 2000, f"connection-status too slow: {elapsed_ms:.1f}ms"


def test_env_only_bundle_has_no_truelayer() -> None:
    bundle = _env_only_bundle()
    assert bundle.lunchflow.provider == "lunchflow"
    assert bundle.quickfile.configured in (True, False)
    flags = light_integration_flags()
    assert "quickfile" in flags
    assert "lunchflow" in flags
