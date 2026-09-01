"""Dashboard live refresh skips recent syncs and runs balances-only when stale."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

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
    called = {"budget": False}

    async def mark_budget(_db):
        called["budget"] = True
        return None

    monkeypatch.setattr(
        "app.services.finance.finance_budget_plan_service.finance_budget_plan_service.ensure_active_from_suggestion",
        mark_budget,
    )
    return called


class _Db:
    async def commit(self):
        return None

    async def rollback(self):
        return None


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

    async def fail_sync(*_a, **_k):
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
        "app.services.finance.finance_live_refresh_service.quickfile_sync_service.sync_balances",
        fail_sync,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_sync_service.sync",
        fail_sync,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_sync_service.sync_balances",
        fail_sync,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_liabilities_service.ensure_from_accounts",
        mark_debts,
    )

    await service.ensure_fresh(_Db())
    assert called["debts"] is True
    assert extras["budget"] is True


@pytest.mark.asyncio
async def test_force_quickfile_reports_syncs_even_when_last_sync_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /live-refresh must re-pull P&L + BS even if last_sync_at is <15 min."""
    service = FinanceLiveRefreshService()
    called = {"qf_balances": 0, "include_reports": None, "lf": 0}
    extras = _patch_live_side_effects(monkeypatch)

    async def recent_status(_db):
        return SimpleNamespace(
            configured=True,
            last_sync_at=datetime.now(timezone.utc).isoformat(),
        )

    async def fake_config(_db):
        return object()

    async def fake_qf_balances(_db, _config, **kwargs):
        called["qf_balances"] += 1
        called["include_reports"] = kwargs.get("include_reports")
        return QuickFileSyncResult(
            accounts_synced=2,
            debtors_gbp=1,
            reports_synced=True,
            message="qf+reports",
        )

    async def fail_qf_full(*_a, **_k):
        raise AssertionError("must not call full QuickFile sync()")

    async def fail_lf(*_a, **_k):
        raise AssertionError("Lunch Flow should stay skipped when last_sync is fresh")

    async def mark_debts(_db):
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
        "app.services.finance.finance_live_refresh_service.quickfile_settings_service.get_config",
        fake_config,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.quickfile_settings_service.is_quota_blocked",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.quickfile_sync_service.sync_balances",
        fake_qf_balances,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.quickfile_sync_service.sync",
        fail_qf_full,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_sync_service.sync",
        fail_lf,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_sync_service.sync_balances",
        fail_lf,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_liabilities_service.ensure_from_accounts",
        mark_debts,
    )

    await service.ensure_fresh(_Db(), force_quickfile_reports=True)
    assert called["qf_balances"] == 1
    assert called["include_reports"] is True
    assert extras["budget"] is True


@pytest.mark.asyncio
async def test_ensure_fresh_uses_quickfile_balances_not_full_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FinanceLiveRefreshService()
    called = {"qf_balances": 0, "qf_full": 0, "lf": 0, "include_reports": None}

    async def empty_status(_db):
        return SimpleNamespace(configured=True, last_sync_at=None)

    async def fake_config(_db):
        return object()

    async def fake_qf_balances(_db, _config, **kwargs):
        called["qf_balances"] += 1
        called["include_reports"] = kwargs.get("include_reports", False)
        return QuickFileSyncResult(accounts_synced=2, debtors_gbp=1, message="qf")

    async def fail_qf_full(_db, _config, **_kwargs):
        called["qf_full"] += 1
        raise AssertionError("live refresh must not call full QuickFile sync()")

    async def fake_lf(_db, _config):
        called["lf"] += 1
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
        "app.services.finance.finance_live_refresh_service.quickfile_settings_service.is_quota_blocked",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.quickfile_sync_service.sync_balances",
        fake_qf_balances,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.quickfile_sync_service.sync",
        fail_qf_full,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_sync_service.sync_balances",
        fake_lf,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_sync_service.sync",
        fake_lf,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_liabilities_service.ensure_from_accounts",
        mark_debts,
    )

    await service.ensure_fresh(_Db())
    assert called["qf_balances"] == 1
    assert called["qf_full"] == 0
    assert called["lf"] == 1
    assert called["include_reports"] is False
    assert extras["budget"] is True
