"""Unit tests for fast Connections status / light health paths."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.services.finance.connection_status_service import (
    _env_only_bundle,
    light_integration_flags,
    load_connection_statuses,
)
from app.services.finance.finance_health_service import finance_health_service
from tests.conftest import login


@pytest.mark.asyncio
async def test_light_health_skips_db_and_is_instant(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    started = time.perf_counter()
    response = await client.get("/finance/health?light=1")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body.get("light") is True
    # Honest: light path does not open Neon or run write probes.
    assert body.get("db_read") is None
    assert body.get("db_write") is None
    assert "quickfile" in body["integrations"]
    assert "lunchflow" in body["integrations"]
    assert "truelayer" not in body.get("integrations", {})
    assert elapsed_ms < 500, f"light health too slow: {elapsed_ms:.1f}ms"


def test_probe_light_is_sync_and_has_no_truelayer() -> None:
    body = finance_health_service.probe_light()
    assert body["light"] is True
    assert body["db_write"] is None
    assert "truelayer" not in body["integrations"]


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


@pytest.mark.asyncio
async def test_connection_status_times_out_to_env_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neon stalls must unlock Connections with env-only status, not hang."""

    async def _hang(_db: object) -> object:
        await asyncio.sleep(60)
        raise AssertionError("should have been cancelled by wait_for")

    monkeypatch.setattr(
        "app.services.finance.connection_status_service._load_connection_statuses_from_db",
        _hang,
    )
    monkeypatch.setattr(
        "app.services.finance.connection_status_service._BUNDLE_DB_TIMEOUT_S",
        0.05,
    )
    started = time.perf_counter()
    bundle = await load_connection_statuses(AsyncMock())
    elapsed = time.perf_counter() - started
    assert elapsed < 2.0, f"timeout fallback too slow: {elapsed:.2f}s"
    assert bundle.lunchflow.provider == "lunchflow"
    assert isinstance(bundle.quickfile.configured, bool)
