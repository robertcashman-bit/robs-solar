"""Stored finance GETs must not wait on live QuickFile / Lunch Flow sync."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_accounts_default_skips_live_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.finance.finance_accounts_service import FinanceAccountsService

    called = {"n": 0}

    async def boom(_db):
        called["n"] += 1
        raise AssertionError("ensure_fresh must not run for stored reads")

    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_live_refresh_service.ensure_fresh",
        boom,
    )

    class _Result:
        def all(self):
            return []

    class _Db:
        async def scalars(self, _stmt):
            return _Result()

    rows = await FinanceAccountsService().list_accounts(_Db())  # type: ignore[arg-type]
    assert rows == []
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_ensure_fresh_default_uses_balance_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.finance.finance_live_refresh_service import FinanceLiveRefreshService

    called = {"balances": 0, "full": 0}

    async def stale_status(_db):
        from types import SimpleNamespace

        return SimpleNamespace(configured=True, last_sync_at=None)

    async def fake_config(_db):
        return object()

    async def fake_balances(_db, _config):
        called["balances"] += 1

    async def fake_full(_db, _config):
        called["full"] += 1

    async def noop_qf(_db, _config, **_kwargs):
        return None

    async def noop_reports(_db):
        return None

    async def noop_debts(_db):
        return 0

    async def noop_budget(_db):
        return None

    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.quickfile_settings_service.get_status",
        stale_status,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_settings_service.get_status",
        stale_status,
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
        noop_qf,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_sync_service.sync_balances",
        fake_balances,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.lunchflow_sync_service.sync",
        fake_full,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_liabilities_service.ensure_from_accounts",
        noop_debts,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_budget_plan_service.finance_budget_plan_service.ensure_active_from_suggestion",
        noop_budget,
    )

    class _Reports:
        async def get_or_refresh_reports(self, _db):
            return await noop_reports(_db)

    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_reports_service",
        _Reports(),
    )

    class _Db:
        async def commit(self):
            return None

        async def rollback(self):
            return None

    await FinanceLiveRefreshService().ensure_fresh(_Db())
    assert called["balances"] == 1
    assert called["full"] == 0
