"""Daily cron refreshes QuickFile and Lunch Flow when env credentials exist."""

import pytest

from app.schemas.finance import LunchFlowSyncResult, QuickFileConfigStatus, QuickFileSyncResult
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

    async def needs_deep(_db) -> bool:
        return False

    async def fake_qf_sync(_db, _config, **kwargs):
        assert kwargs.get("incremental_only") is True
        assert kwargs.get("force_full") is not True
        return QuickFileSyncResult(accounts_synced=2, debtors_gbp=1.0, message="qf ok")

    async def fake_lf_sync(_db, _config):
        return LunchFlowSyncResult(accounts_synced=5, message="lf ok")

    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.get_config",
        fake_qf_config,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.needs_deep_history_extension",
        needs_deep,
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


@pytest.mark.asyncio
async def test_daily_sync_force_full_when_lookback_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When stored lookback is missing or < 730, cron runs force_full once."""
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
        lambda: False,
    )

    async def fake_qf_config(_db):
        return object()

    async def needs_deep(_db) -> bool:
        return True

    async def not_blocked(_db) -> bool:
        return False

    captured: dict[str, object] = {}

    async def fake_qf_sync(_db, _config, **kwargs):
        captured["kwargs"] = kwargs
        return QuickFileSyncResult(
            accounts_synced=1,
            debtors_gbp=0.0,
            message="730-day force-full sync",
        )

    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.get_config",
        fake_qf_config,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.needs_deep_history_extension",
        needs_deep,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.is_quota_blocked",
        not_blocked,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_sync_service.sync",
        fake_qf_sync,
    )
    result = await FinanceDailySyncService().sync_once()
    assert result.ok is True
    assert captured["kwargs"].get("force_full") is True
    assert captured["kwargs"].get("incremental_only") is not True
    assert "force-full" in result.quickfile


@pytest.mark.asyncio
async def test_daily_sync_incremental_when_lookback_already_two_years(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When stored lookback is already >= 730, cron stays incremental-only."""
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
        lambda: False,
    )

    async def fake_qf_config(_db):
        return object()

    async def needs_deep(_db) -> bool:
        return False

    captured: dict[str, object] = {}

    async def fake_qf_sync(_db, _config, **kwargs):
        captured["kwargs"] = kwargs
        return QuickFileSyncResult(
            accounts_synced=1,
            debtors_gbp=0.0,
            message="90-day incremental",
        )

    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.get_config",
        fake_qf_config,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.needs_deep_history_extension",
        needs_deep,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_sync_service.sync",
        fake_qf_sync,
    )
    result = await FinanceDailySyncService().sync_once()
    assert result.ok is True
    assert captured["kwargs"].get("incremental_only") is True
    assert captured["kwargs"].get("force_full") is not True
    assert "incremental" in result.quickfile


@pytest.mark.asyncio
async def test_daily_sync_skips_deep_import_when_quota_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quota exhausted: report message and do not call force_full."""
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
        lambda: False,
    )

    sync_called = False

    async def fake_qf_config(_db):
        return object()

    async def needs_deep(_db) -> bool:
        return True

    async def blocked(_db) -> bool:
        return True

    async def status(_db):
        return QuickFileConfigStatus(
            account_number="1",
            api_key_set=True,
            application_id="a",
            configured=True,
            connected=True,
            last_error="API request limit exceeded (1000)",
            quota_exhausted_at="2026-08-20T06:00:00+00:00",
        )

    async def fake_qf_sync(*_a, **_k):
        nonlocal sync_called
        sync_called = True
        raise AssertionError("sync must not run when quota is blocked")

    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.get_config",
        fake_qf_config,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.needs_deep_history_extension",
        needs_deep,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.is_quota_blocked",
        blocked,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_settings_service.get_status",
        status,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_daily_sync_service.quickfile_sync_service.sync",
        fake_qf_sync,
    )
    result = await FinanceDailySyncService().sync_once()
    assert result.ok is True
    assert sync_called is False
    assert "quota exhausted" in result.quickfile.lower()
