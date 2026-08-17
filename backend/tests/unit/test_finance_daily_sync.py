"""Daily cron refreshes QuickFile and Lunch Flow when env credentials exist."""

import pytest

from app.schemas.finance import LunchFlowSyncResult, QuickFileSyncResult
from app.services.finance.finance_daily_sync_service import FinanceDailySyncService


class _FakeDb:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_daily_sync_skips_when_nothing_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.SessionLocal",
        lambda: _FakeDb(),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.env_configured",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.lunchflow_settings_service.env_configured",
        lambda: False,
    )
    result = await FinanceDailySyncService().sync_once()
    assert result.ok is True
    assert "skipped" in result.quickfile
    assert "skipped" in result.lunchflow


@pytest.mark.asyncio
async def test_daily_sync_runs_configured_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.SessionLocal",
        lambda: _FakeDb(),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.env_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.lunchflow_settings_service.env_configured",
        lambda: True,
    )

    async def fake_qf_config(_db):
        return object()

    async def fake_lf_config(_db):
        return object()

    async def fake_qf_sync(_db, _config):
        return QuickFileSyncResult(accounts_synced=2, debtors_gbp=1.0, message="qf ok")

    async def fake_lf_sync(_db, _config):
        return LunchFlowSyncResult(accounts_synced=5, message="lf ok")

    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.get_config",
        fake_qf_config,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.lunchflow_settings_service.get_config",
        fake_lf_config,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_sync_service.sync",
        fake_qf_sync,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.lunchflow_sync_service.sync",
        fake_lf_sync,
    )
    result = await FinanceDailySyncService().sync_once()
    assert result.ok is True
    assert result.quickfile == "qf ok"
    assert result.lunchflow == "lf ok"
