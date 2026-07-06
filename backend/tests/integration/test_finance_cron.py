"""Tests for Vercel Cron finance daily sync endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cron_daily_sync_requires_secret(client: AsyncClient) -> None:
    response = await client.get("/finance/cron/daily-sync")
    assert response.status_code in (401, 503)


@pytest.mark.asyncio
async def test_cron_daily_sync_with_valid_secret(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "cron_secret", "test-cron-secret")
    response = await client.get(
        "/finance/cron/daily-sync",
        headers={"Authorization": "Bearer test-cron-secret"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "open_banking" in body
    assert "quickfile" in body
    assert "ok" in body


@pytest.mark.asyncio
async def test_cron_daily_sync_rejects_wrong_secret(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "cron_secret", "test-cron-secret")
    response = await client.get(
        "/finance/cron/daily-sync",
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401
