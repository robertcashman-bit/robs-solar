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
async def test_overview_live_query_forces_quickfile_reports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /overview?live=1 must force QF BS pull (same as POST /live-refresh)."""
    from app.services.finance.finance_overview_service import FinanceOverviewService

    called = {"force": None}

    async def capture_ensure(_db, **kwargs):
        called["force"] = kwargs.get("force_quickfile_reports")
        return {
            "quickfile_reports_synced": True,
            "partial_failure": False,
            "warnings": [],
        }

    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_live_refresh_service.ensure_fresh",
        capture_ensure,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_overview_cache_service.finance_overview_cache_service.clear",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_overview_cache_service.finance_overview_cache_service.read",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_overview_cache_service.finance_overview_cache_service.write",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_overview_cache_service.finance_overview_cache_service.fingerprint",
        AsyncMock(return_value="fp"),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_overview_service.finance_accounts_service.list_accounts",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_overview_service.finance_liabilities_service.list_liabilities",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_overview_service.finance_liabilities_service.ensure_from_accounts",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        FinanceOverviewService,
        "personal_snapshot_for_month",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        FinanceOverviewService,
        "business_snapshot_for_month",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        FinanceOverviewService,
        "_open_banking_flow",
        AsyncMock(return_value=SimpleNamespace(income_gbp=0.0, spending_gbp=0.0)),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_insights_service.finance_insights_service.refresh_for_overview",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.finance.finance_ledger_service.finance_ledger_service.period_flow_totals",
        AsyncMock(
            return_value={
                "period": "1m",
                "scope": "personal",
                "label": "1 month",
                "date_from": "2026-08-01",
                "date_to": "2026-08-31",
                "months_requested": 1,
                "months_with_data": 0,
                "month_keys": ["2026-08"],
                "transaction_count": 0,
                "income_gbp": 0.0,
                "spending_gbp": 0.0,
                "surplus_gbp": 0.0,
                "history_partial": False,
                "coverage_note": "",
            }
        ),
    )
    monkeypatch.setattr(
        FinanceOverviewService,
        "_quickfile_period_totals",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        FinanceOverviewService,
        "_quickfile_balance_sheet",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        FinanceOverviewService,
        "_sync_stamp",
        AsyncMock(return_value=None),
    )

    class _Db:
        async def scalars(self, _stmt):
            return SimpleNamespace(all=lambda: [], one=lambda: (0, 0.0, None), first=lambda: None)

        async def scalar(self, _stmt):
            return None

        async def execute(self, _stmt):
            return SimpleNamespace(all=lambda: [], one=lambda: (0, 0.0, None), first=lambda: None)

        async def get(self, *_a, **_k):
            return None

        async def commit(self):
            return None

        async def rollback(self):
            return None

        def add(self, *_a, **_k):
            return None

    await FinanceOverviewService().get_overview(
        _Db(),  # type: ignore[arg-type]
        month="2026-09",
        refresh_live=True,
    )
    assert called["force"] is True


@pytest.mark.asyncio
async def test_force_reports_partial_failure_when_reports_not_synced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Balances OK + reports failed must surface partial_failure, not invent BS."""
    service = FinanceLiveRefreshService()
    _patch_live_side_effects(monkeypatch)

    async def recent_status(_db):
        return SimpleNamespace(
            configured=True,
            last_sync_at=datetime.now(timezone.utc).isoformat(),
        )

    async def fake_config(_db):
        return object()

    async def fake_qf_balances(_db, _config, **kwargs):
        assert kwargs.get("include_reports") is True
        return QuickFileSyncResult(
            accounts_synced=2,
            debtors_gbp=1,
            reports_synced=False,
            message="qf balances only",
        )

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
        "app.services.finance.finance_live_refresh_service.finance_liabilities_service.ensure_from_accounts",
        mark_debts,
    )

    status = await service.ensure_fresh(_Db(), force_quickfile_reports=True)
    assert status["quickfile_reports_synced"] is False
    assert status["partial_failure"] is True
    assert any("balance sheet" in w.lower() for w in status["warnings"])


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
