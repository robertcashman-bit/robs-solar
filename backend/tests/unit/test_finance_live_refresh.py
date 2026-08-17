"""Dashboard live refresh skips recent syncs and runs when data is stale."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.schemas.finance import LunchFlowSyncResult, QuickFileSyncResult
from app.services.finance.finance_live_refresh_service import (
    FinanceLiveRefreshService,
    is_stale,
)


def test_is_stale_treats_missing_and_invalid_as_stale() -> None:
    assert is_stale(None) is True
    assert is_stale("") is True
    assert is_stale("already") is True


def test_is_stale_respects_recent_iso_timestamp() -> None:
    recent = datetime.now(timezone.utc).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    assert is_stale(recent) is False
    assert is_stale(old) is True


def _patch_live_side_effects(monkeypatch: pytest.MonkeyPatch) -> dict:
    called = {"budget": False, "reports": False}

    async def mark_budget(_db):
        called["budget"] = True
        return None

    async def mark_reports(_db):
        called["reports"] = True
        return None

    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_reports_service.get_or_refresh_reports",
        mark_reports,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_budget_plan_service.finance_budget_plan_service.ensure_active_from_suggestion",
        mark_budget,
    )
    return called


@pytest.mark.asyncio
async def test_ensure_fresh_skips_recent_syncs(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FinanceLiveRefreshService()
    called = {"qf": False, "lf": False, "debts": False}
    extras = _patch_live_side_effects(monkeypatch)

    async def recent_status(_db):
        return SimpleNamespace(
            configured=True,
            last_sync_at=datetime.now(timezone.utc).isoformat(),
        )

    async def fail_sync(_db, _config):
        raise AssertionError("should not sync")

    async def mark_debts(_db):
        called["debts"] = True
        return 0

    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.quickfile_settings_service.get_status",
        recent_status,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_settings_service.get_status",
        recent_status,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.quickfile_sync_service.sync",
        fail_sync,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_sync_service.sync",
        fail_sync,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_liabilities_service.ensure_from_accounts",
        mark_debts,
    )

    class _Db:
        async def commit(self):
            return None

        async def rollback(self):
            return None

    await service.ensure_fresh(_Db())
    assert called["debts"] is True
    assert extras["budget"] is True
    assert extras["reports"] is True


@pytest.mark.asyncio
async def test_ensure_fresh_syncs_when_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FinanceLiveRefreshService()
    called = {"qf": False, "lf": False}

    async def empty_status(_db):
        return SimpleNamespace(configured=True, last_sync_at=None)

    async def fake_config(_db):
        return object()

    async def fake_qf(_db, _config):
        called["qf"] = True
        return QuickFileSyncResult(accounts_synced=2, debtors_gbp=1, message="qf")

    async def fake_lf(_db, _config):
        called["lf"] = True
        return LunchFlowSyncResult(accounts_synced=5, message="lf")

    async def mark_debts(_db):
        return 0

    extras = _patch_live_side_effects(monkeypatch)

    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.quickfile_settings_service.get_status",
        empty_status,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_settings_service.get_status",
        empty_status,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.quickfile_settings_service.get_config",
        fake_config,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_settings_service.get_config",
        fake_config,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.quickfile_sync_service.sync",
        fake_qf,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_sync_service.sync",
        fake_lf,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_liabilities_service.ensure_from_accounts",
        mark_debts,
    )

    class _Db:
        async def commit(self):
            return None

        async def rollback(self):
            return None

    await service.ensure_fresh(_Db())
    assert called == {"qf": True, "lf": True}
    assert extras["budget"] is True
    assert extras["reports"] is True
