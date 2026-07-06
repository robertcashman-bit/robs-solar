"""Unit tests for finance daily background sync."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.finance import finance_daily_sync_service


@pytest.mark.asyncio
async def test_sync_once_calls_configured_integrations() -> None:
    ob_result = type("Result", (), {"message": "ob ok"})()
    qf_result = type("Result", (), {"message": "qf ok", "accounts_synced": 2})()

    with (
        patch.object(
            finance_daily_sync_service,
            "_mark_expired_sessions",
            new=AsyncMock(),
        ),
        patch.object(
            finance_daily_sync_service.open_banking_settings_service,
            "get_config",
            new=AsyncMock(return_value=object()),
        ),
        patch.object(
            finance_daily_sync_service.open_banking_settings_service,
            "is_configured",
            return_value=True,
        ),
        patch.object(
            finance_daily_sync_service.open_banking_sync_service,
            "sync",
            new=AsyncMock(return_value=ob_result),
        ) as ob_sync,
        patch.object(
            finance_daily_sync_service.quickfile_settings_service,
            "get_config",
            new=AsyncMock(return_value=object()),
        ),
        patch.object(
            finance_daily_sync_service.quickfile_settings_service,
            "get_status",
            new=AsyncMock(return_value=type("Status", (), {"configured": True})()),
        ),
        patch.object(
            finance_daily_sync_service.quickfile_sync_service,
            "sync",
            new=AsyncMock(return_value=qf_result),
        ) as qf_sync,
    ):
        await finance_daily_sync_service.sync_once()

    ob_sync.assert_awaited_once()
    qf_sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_once_returns_structured_result() -> None:
    with (
        patch.object(
            finance_daily_sync_service,
            "_mark_expired_sessions",
            new=AsyncMock(),
        ),
        patch.object(
            finance_daily_sync_service.open_banking_settings_service,
            "get_config",
            new=AsyncMock(return_value=object()),
        ),
        patch.object(
            finance_daily_sync_service.open_banking_settings_service,
            "is_configured",
            return_value=False,
        ),
        patch.object(
            finance_daily_sync_service.quickfile_settings_service,
            "get_config",
            new=AsyncMock(return_value=object()),
        ),
        patch.object(
            finance_daily_sync_service.quickfile_settings_service,
            "get_status",
            new=AsyncMock(return_value=type("Status", (), {"configured": False})()),
        ),
    ):
        result = await finance_daily_sync_service.sync_once()

    assert result.ok is True
    assert "skipped" in result.open_banking.lower()


@pytest.mark.asyncio
async def test_start_and_stop_finance_daily_sync() -> None:
    from app.config import settings

    original_enabled = settings.finance_daily_sync_enabled
    original_hours = settings.finance_daily_sync_interval_hours
    original_secret = settings.cron_secret
    settings.finance_daily_sync_enabled = True
    settings.finance_daily_sync_interval_hours = 24
    settings.cron_secret = ""

    with patch.object(finance_daily_sync_service, "sync_once", new=AsyncMock()):
        with patch.object(finance_daily_sync_service.asyncio, "sleep", new=AsyncMock()):
            task = finance_daily_sync_service.start_finance_daily_sync()
            assert task is not None
            assert finance_daily_sync_service.start_finance_daily_sync() is task
            await finance_daily_sync_service.stop_finance_daily_sync()

    settings.finance_daily_sync_enabled = original_enabled
    settings.finance_daily_sync_interval_hours = original_hours
    settings.cron_secret = original_secret


def test_start_finance_daily_sync_disabled_returns_none() -> None:
    from app.config import settings

    original = settings.finance_daily_sync_enabled
    settings.finance_daily_sync_enabled = False
    try:
        assert finance_daily_sync_service.start_finance_daily_sync() is None
    finally:
        settings.finance_daily_sync_enabled = original


def test_start_finance_daily_sync_skips_loop_when_cron_secret_set() -> None:
    from app.config import settings

    original_enabled = settings.finance_daily_sync_enabled
    original_secret = settings.cron_secret
    settings.finance_daily_sync_enabled = True
    settings.cron_secret = "production-cron-secret"
    try:
        assert finance_daily_sync_service.start_finance_daily_sync() is None
    finally:
        settings.finance_daily_sync_enabled = original_enabled
        settings.cron_secret = original_secret
