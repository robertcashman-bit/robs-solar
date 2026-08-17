"""Auto-refresh stored QuickFile reports when env credentials are present."""

import pytest

from app.schemas.finance import QuickFileConfig, QuickFileReportsResponse
from app.services.finance.quickfile_reports_service import QuickFileReportsService


@pytest.mark.asyncio
async def test_get_or_refresh_returns_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    service = QuickFileReportsService()
    from datetime import datetime, timezone

    stored = QuickFileReportsResponse(synced_at=datetime.now(timezone.utc).isoformat())

    async def fake_stored(_db):
        return stored

    monkeypatch.setattr(service, "get_stored_reports", fake_stored)
    assert await service.get_or_refresh_reports(object()) is stored


@pytest.mark.asyncio
async def test_get_or_refresh_skips_when_env_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    service = QuickFileReportsService()
    called = {"sync": False}

    async def fake_stored(_db):
        return None

    async def fake_sync(_db, _config):
        called["sync"] = True
        return QuickFileReportsResponse(synced_at="live")

    monkeypatch.setattr(service, "get_stored_reports", fake_stored)
    monkeypatch.setattr(service, "sync_reports", fake_sync)
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_settings_service.env_configured",
        lambda: False,
    )
    assert await service.get_or_refresh_reports(object()) is None
    assert called["sync"] is False


@pytest.mark.asyncio
async def test_get_or_refresh_pulls_when_env_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = QuickFileReportsService()
    live = QuickFileReportsResponse(synced_at="live")

    async def fake_stored(_db):
        return None

    async def fake_config(_db):
        return QuickFileConfig(account_number="1", api_key="k", application_id="a")

    async def fake_sync(_db, _config):
        return live

    monkeypatch.setattr(service, "get_stored_reports", fake_stored)
    monkeypatch.setattr(service, "sync_reports", fake_sync)
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_settings_service.env_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_settings_service.get_config",
        fake_config,
    )
    assert await service.get_or_refresh_reports(object()) is live


@pytest.mark.asyncio
async def test_get_or_refresh_replaces_stale_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = QuickFileReportsService()
    stored = QuickFileReportsResponse(synced_at="2020-01-01T00:00:00+00:00")
    live = QuickFileReportsResponse(synced_at="live")

    async def fake_stored(_db):
        return stored

    async def fake_config(_db):
        return QuickFileConfig(account_number="1", api_key="k", application_id="a")

    async def fake_sync(_db, _config):
        return live

    monkeypatch.setattr(service, "get_stored_reports", fake_stored)
    monkeypatch.setattr(service, "sync_reports", fake_sync)
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_settings_service.env_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_settings_service.get_config",
        fake_config,
    )
    assert await service.get_or_refresh_reports(object()) is live
