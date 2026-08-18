"""QuickFile sync_balances never imports Bank_Search history."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.integrations.quickfile_client import QuickFileError
from app.schemas.finance import QuickFileConfig, QuickFileSyncResult
from app.services.finance.quickfile_sync_service import QuickFileSyncService


class _Db:
    async def commit(self) -> None:
        return None

    async def scalar(self, _stmt):
        return None

    def add(self, _row) -> None:
        return None


@pytest.mark.asyncio
async def test_sync_balances_skips_transactions(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"tx": 0}

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
                    "balance_gbp": 10.0,
                    "external_id": "1200",
                    "notes": "",
                }
            ]

        async def fetch_debtors_gbp(self) -> float:
            return 5.0

        async def sync_transactions(self, *, since=None):
            called["tx"] += 1
            raise AssertionError("sync_balances must not call sync_transactions")

    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.QuickFileProvider", FakeProvider
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.is_quota_blocked",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.get_budget_account_ids",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.mark_synced",
        AsyncMock(),
    )

    result = await QuickFileSyncService().sync_balances(
        _Db(),
        QuickFileConfig(account_number="1", api_key="k", application_id="a"),
    )
    assert isinstance(result, QuickFileSyncResult)
    assert result.imported == 0
    assert called["tx"] == 0
    assert "balances" in result.message.lower()


@pytest.mark.asyncio
async def test_sync_balances_records_quota_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProvider:
        def __init__(self, _config) -> None:
            pass

        async def sync_accounts(self):
            raise QuickFileError("API request limit exceeded (1000)")

        async def fetch_debtors_gbp(self) -> float:
            return 0.0

    record = AsyncMock()
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.QuickFileProvider", FakeProvider
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.is_quota_blocked",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.quickfile_settings_service.record_error",
        record,
    )

    with pytest.raises(QuickFileError, match="API request limit exceeded"):
        await QuickFileSyncService().sync_balances(
            _Db(),
            QuickFileConfig(account_number="1", api_key="k", application_id="a"),
        )
    record.assert_awaited()
