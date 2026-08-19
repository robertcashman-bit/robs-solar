"""Lunch Flow and QuickFile first-sync vs incremental lookbacks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.finance import (
    LunchFlowConfig,
    LunchFlowSyncResult,
    QuickFileConfig,
    QuickFileSyncResult,
)
from app.services.finance.lunchflow_sync_service import LunchFlowSyncService
from app.services.finance.quickfile_sync_service import QuickFileSyncService


class _Db:
    async def flush(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def scalar(self, _stmt):
        return None

    async def scalars(self, _stmt):
        class _Result:
            def all(self):
                return []

        return _Result()

    def add(self, _row) -> None:
        return None


@pytest.mark.asyncio
async def test_lunchflow_first_sync_uses_365_day_since(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str | None] = {}

    class FakeProvider:
        def __init__(self, _config) -> None:
            pass

        async def sync_accounts(self):
            return [
                {
                    "scope": "personal",
                    "account_type": "current",
                    "name": "Current",
                    "provider": "Lunch Flow",
                    "balance_gbp": 10.0,
                    "external_id": "lf-1",
                    "notes": "",
                }
            ]

        async def sync_transactions(self, *, since=None):
            captured["since"] = since
            return [
                {
                    "posted_on": "2026-01-15",
                    "amount_gbp": -12.0,
                    "description": "SHOP",
                    "account_external_id": "lf-1",
                    "account_name": "Current",
                    "external_id": "tx-1",
                    "scope": "personal",
                    "currency": "GBP",
                }
            ]

    async def needs_full(_db) -> bool:
        return True

    async def mark_full(_db) -> None:
        captured["marked_full"] = "1"

    async def mark_synced(_db) -> None:
        return None

    async def monthly_flow(*_a, **_k):
        return 0.0, 0.0

    async def commit(db, rows, *, source, actor="import", persist=True):
        assert source == "lunchflow"
        assert len(rows) == 1
        return {"imported": 1, "duplicate_count": 0, "rejected_count": 0}

    async def fake_backup(*_a, **_k):
        return None

    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.LunchFlowProvider", FakeProvider
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.lunchflow_settings_service.needs_full_history_import",
        needs_full,
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.lunchflow_settings_service.mark_full_history_imported",
        mark_full,
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.lunchflow_settings_service.mark_synced",
        mark_synced,
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.finance_ledger_service.monthly_flow",
        monthly_flow,
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.finance_import_service.commit",
        commit,
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service._safe_backup",
        fake_backup,
    )

    result = await LunchFlowSyncService().sync(_Db(), LunchFlowConfig(api_key="k"))
    assert isinstance(result, LunchFlowSyncResult)
    assert captured["marked_full"] == "1"
    expected = (datetime.now(timezone.utc) - timedelta(days=365)).date().isoformat()
    assert captured["since"] == expected
    assert "365-day" in result.message


@pytest.mark.asyncio
async def test_lunchflow_incremental_uses_90_day_since(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str | None] = {}

    class FakeProvider:
        def __init__(self, _config) -> None:
            pass

        async def sync_accounts(self):
            return []

        async def sync_transactions(self, *, since=None):
            captured["since"] = since
            return []

    async def needs_full(_db) -> bool:
        return False

    async def commit(db, rows, *, source, actor="import", persist=True):
        return {"imported": 0, "duplicate_count": 0, "rejected_count": 0}

    async def noop(_db) -> None:
        return None

    async def monthly_flow(*_a, **_k):
        return 0.0, 0.0

    async def fake_backup(*_a, **_k):
        return None

    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.LunchFlowProvider", FakeProvider
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.lunchflow_settings_service.needs_full_history_import",
        needs_full,
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.lunchflow_settings_service.mark_synced",
        noop,
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.finance_ledger_service.monthly_flow",
        monthly_flow,
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.finance_import_service.commit",
        commit,
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service._safe_backup",
        fake_backup,
    )

    result = await LunchFlowSyncService().sync(_Db(), LunchFlowConfig(api_key="k"))
    expected = (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()
    assert captured["since"] == expected
    assert "90-day" in result.message


@pytest.mark.asyncio
async def test_quickfile_first_sync_commits_with_deep_lookback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeProvider:
        def __init__(self, _config) -> None:
            pass

        async def sync_accounts(self):
            return [
                {
                    "scope": "business",
                    "account_type": "current",
                    "name": "Business",
                    "provider": "QuickFile",
                    "balance_gbp": 1.0,
                    "external_id": "1200",
                    "notes": "",
                }
            ]

        async def fetch_debtors_gbp(self) -> float:
            return 0.0

        async def sync_transactions(self, *, since=None):
            captured["since"] = since
            return [
                {
                    "posted_on": "2026-07-01",
                    "amount_gbp": -25.0,
                    "description": "SUPPLIER",
                    "account_external_id": "1200",
                    "account_name": "Business",
                    "external_id": "qf-1",
                    "scope": "business",
                    "currency": "GBP",
                }
            ]

    async def needs_full(_db) -> bool:
        return True

    async def mark_full(_db, **_kwargs) -> None:
        captured["marked_full"] = True

    async def noop(_db) -> None:
        return None

    async def budget_ids(_db):
        return []

    async def commit(db, rows, *, source, actor="import", persist=True):
        assert source == "quickfile"
        captured["rows"] = rows
        return {"imported": 1, "duplicate_count": 0, "rejected_count": 0}

    async def fake_reports(*_a, **_k):
        return None

    async def fake_backup(*_a, **_k):
        return None

    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.QuickFileProvider", FakeProvider
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.needs_full_history_import",
        needs_full,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.mark_full_history_imported",
        mark_full,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.mark_synced",
        noop,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.get_budget_account_ids",
        budget_ids,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.finance_import_service.commit",
        commit,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_reports_service.sync_reports",
        fake_reports,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service._safe_backup",
        fake_backup,
    )

    result = await QuickFileSyncService().sync(
        _Db(),
        QuickFileConfig(account_number="1", api_key="k", application_id="a"),
        include_reports=False,
        backup=False,
    )
    assert isinstance(result, QuickFileSyncResult)
    assert result.imported == 1
    assert captured["marked_full"] is True
    from app.services.finance.sync_lookback import QUICKFILE_INITIAL_LOOKBACK_DAYS

    expected = (
        datetime.now(timezone.utc) - timedelta(days=QUICKFILE_INITIAL_LOOKBACK_DAYS)
    ).date().isoformat()
    assert captured["since"] == expected
    assert f"{QUICKFILE_INITIAL_LOOKBACK_DAYS}-day" in result.message


@pytest.mark.asyncio
async def test_quickfile_force_full_uses_ten_year_lookback_without_clearing_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """force_full must not wipe markers before the import finishes.

    Clearing up front left production with a stale last_sync when the Vercel
    default 300s maxDuration killed the request mid year-chunk walk.
    """
    captured: dict[str, object] = {
        "cleared": False,
        "commit_calls": 0,
        "windows": [],
    }

    class FakeProvider:
        def __init__(self, _config) -> None:
            pass

        async def sync_accounts(self):
            return []

        async def fetch_debtors_gbp(self) -> float:
            return 0.0

        async def sync_transactions(self, *, since=None, until=None):
            captured["windows"].append((since, until))
            return [
                {
                    "amount_gbp": -1.0,
                    "date": (since or "2020-01-01")[:10],
                    "posted_on": (since or "2020-01-01")[:10],
                    "description": "chunk",
                    "external_id": f"tx-{since}-{until}",
                    "account_external_id": "1200",
                    "account_name": "Current",
                    "currency": "GBP",
                    "scope": "business",
                }
            ]

    async def clear_full(_db) -> None:
        captured["cleared"] = True

    async def needs_full(_db) -> bool:
        return False

    async def mark_full(_db, **_kwargs) -> None:
        captured["marked_full"] = True
        captured["lookback"] = _kwargs.get("lookback_days")

    async def noop(_db) -> None:
        return None

    async def budget_ids(_db):
        return []

    async def commit(db, rows, *, source, actor="import", persist=True):
        captured["commit_calls"] = int(captured["commit_calls"]) + 1
        return {
            "imported": len(rows),
            "duplicate_count": 0,
            "rejected_count": 0,
        }

    async def fake_backup(*_a, **_k):
        return None

    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.QuickFileProvider", FakeProvider
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.clear_full_history_import",
        clear_full,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.needs_full_history_import",
        needs_full,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.mark_full_history_imported",
        mark_full,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.mark_synced",
        noop,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.get_budget_account_ids",
        budget_ids,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.finance_import_service.commit",
        commit,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service._safe_backup",
        fake_backup,
    )

    result = await QuickFileSyncService().sync(
        _Db(),
        QuickFileConfig(account_number="1", api_key="k", application_id="a"),
        include_reports=False,
        backup=False,
        force_full=True,
    )
    from app.services.finance.sync_lookback import QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS

    assert captured["cleared"] is False
    assert captured["marked_full"] is True
    assert captured["lookback"] == QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS
    assert int(captured["commit_calls"]) >= 2
    assert len(captured["windows"]) >= 2
    expected = (
        datetime.now(timezone.utc) - timedelta(days=QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS)
    ).date().isoformat()
    assert captured["windows"][0][0] == expected
    assert f"{QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS}-day" in result.message
    assert result.imported >= 2


@pytest.mark.asyncio
async def test_quickfile_incremental_uses_90_day_lookback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeProvider:
        def __init__(self, _config) -> None:
            pass

        async def sync_accounts(self):
            return []

        async def fetch_debtors_gbp(self) -> float:
            return 0.0

        async def sync_transactions(self, *, since=None):
            captured["since"] = since
            return []

    async def needs_full(_db) -> bool:
        return False

    async def noop(_db) -> None:
        return None

    async def budget_ids(_db):
        return []

    async def commit(db, rows, *, source, actor="import", persist=True):
        return {"imported": 0, "duplicate_count": 0, "rejected_count": 0}

    async def fake_backup(*_a, **_k):
        return None

    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.QuickFileProvider", FakeProvider
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.needs_full_history_import",
        needs_full,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.mark_synced",
        noop,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.get_budget_account_ids",
        budget_ids,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.finance_import_service.commit",
        commit,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service._safe_backup",
        fake_backup,
    )

    result = await QuickFileSyncService().sync(
        _Db(),
        QuickFileConfig(account_number="1", api_key="k", application_id="a"),
        include_reports=False,
        backup=False,
    )
    expected = (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()
    assert captured["since"] == expected
    assert "90-day" in result.message
