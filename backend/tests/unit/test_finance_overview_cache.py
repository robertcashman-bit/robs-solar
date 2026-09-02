"""Dashboard GET must return persisted figures without live or write-on-read work."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_default_overview_skips_live_refresh_and_budget_seed(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = {"live": 0, "budget": 0, "position": 0}

    async def boom_live(_db, **_kwargs):
        called["live"] += 1
        raise AssertionError("live refresh must not run on default GET")

    async def boom_budget(_db):
        called["budget"] += 1
        return None

    async def boom_position(_db, _overview, month=None):
        called["position"] += 1
        return None

    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_live_refresh_service.ensure_fresh",
        boom_live,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_budget_plan_service.finance_budget_plan_service.ensure_active_from_suggestion",
        boom_budget,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_position_service.finance_position_service.record_from_overview",
        boom_position,
    )

    await login(client, "viewer", "viewer-pass")
    first = await client.get("/finance/overview")
    assert first.status_code == 200
    body = first.json()
    assert "personal_bank_balance_gbp" in body
    assert body.get("cached") is False
    assert called["live"] == 0
    assert called["budget"] == 0
    assert called["position"] == 0

    second = await client.get("/finance/overview")
    assert second.status_code == 200
    cached = second.json()
    assert cached.get("cached") is True
    assert cached["personal_bank_balance_gbp"] == body["personal_bank_balance_gbp"]
    assert cached["monthly_income_gbp"] == body["monthly_income_gbp"]
    assert called["live"] == 0
    assert called["position"] == 0


@pytest.mark.asyncio
async def test_overview_cache_invalidates_when_accounts_change(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    await login(client, "viewer", "viewer-pass")
    before = (await client.get("/finance/overview")).json()["personal_bank_balance_gbp"]

    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]
    created = await client.post(
        "/finance/accounts",
        json={
            "scope": "personal",
            "account_type": "current",
            "name": "Cache bust current",
            "balance_gbp": 123,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201

    await login(client, "viewer", "viewer-pass")
    after = (await client.get("/finance/overview")).json()
    assert after.get("cached") is False
    assert after["personal_bank_balance_gbp"] == round(before + 123, 2)


@pytest.mark.asyncio
async def test_fresh_query_bypasses_overview_cache(
    client: AsyncClient,
) -> None:
    await login(client, "viewer", "viewer-pass")
    first = (await client.get("/finance/overview")).json()
    fresh = (await client.get("/finance/overview?fresh=1")).json()
    assert first.get("cached") is False
    assert fresh.get("cached") is False
    assert fresh["personal_bank_balance_gbp"] == first["personal_bank_balance_gbp"]
    assert isinstance(fresh.get("generated_at"), str)
    generated = datetime.fromisoformat(fresh["generated_at"].replace("Z", "+00:00"))
    assert generated.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_soft_stale_overview_cache_still_returns_last_known(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TTL expiry alone must not force a blank first paint."""
    from datetime import timedelta

    from sqlalchemy import select

    from app.db.models import FinanceOverviewCacheRow
    from app.db.session import SessionLocal
    from app.services.finance import finance_overview_cache_service as cache_mod

    monkeypatch.setattr(cache_mod, "CACHE_TTL", timedelta(seconds=1))

    await login(client, "viewer", "viewer-pass")
    first = await client.get("/finance/overview")
    assert first.status_code == 200
    body = first.json()

    async with SessionLocal() as db:
        row = (await db.scalars(select(FinanceOverviewCacheRow))).first()
        assert row is not None
        row.generated_at = datetime.now(timezone.utc) - timedelta(hours=2)
        await db.commit()

    second = await client.get("/finance/overview")
    assert second.status_code == 200
    cached = second.json()
    assert cached.get("cached") is True
    assert cached["personal_bank_balance_gbp"] == body["personal_bank_balance_gbp"]


@pytest.mark.asyncio
async def test_overview_includes_side_breakdowns_without_live_providers(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = {"live": 0}

    async def boom_live(_db, **_kwargs):
        called["live"] += 1
        raise AssertionError("live refresh must not run on default GET")

    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_live_refresh_service.ensure_fresh",
        boom_live,
    )
    await login(client, "viewer", "viewer-pass")
    body = (await client.get("/finance/overview")).json()
    assert called["live"] == 0
    assert body["personal_breakdown"] is not None
    assert body["business_breakdown"] is not None
    assert body["personal_breakdown"]["side"] == "personal"
    assert body["business_breakdown"]["side"] == "business"
    assert "owned" in body["personal_breakdown"]
    assert "owed" in body["business_breakdown"]

    cached = (await client.get("/finance/overview")).json()
    assert cached.get("cached") is True
    assert cached["personal_breakdown"]["whats_left_gbp"] == body["personal_breakdown"][
        "whats_left_gbp"
    ]


@pytest.mark.asyncio
async def test_cached_overview_returns_fast_when_live_providers_hang(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First-paint cache path must never wait on QuickFile / Lunch Flow."""
    import asyncio
    import time

    await login(client, "viewer", "viewer-pass")
    primed = await client.get("/finance/overview")
    assert primed.status_code == 200
    assert primed.json().get("cached") is False

    async def hang(*_args, **_kwargs):
        await asyncio.sleep(60)
        raise AssertionError("live provider must not be awaited on cache GET")

    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.QuickFileReportsService.fetch_live_reports",
        hang,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.QuickFileReportsService.get_or_refresh_reports",
        hang,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_sync_service.QuickFileSyncService.sync_balances",
        hang,
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.LunchFlowSyncService.sync_balances",
        hang,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_live_refresh_service.ensure_fresh",
        hang,
    )

    started = time.perf_counter()
    second = await client.get("/finance/overview")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert second.status_code == 200
    body = second.json()
    assert body.get("cached") is True
    assert elapsed_ms < 12_000
    # Cache hits should be well under the client abort budget.
    assert elapsed_ms < 3_000


@pytest.mark.asyncio
async def test_get_overview_refresh_live_false_never_calls_live_qf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Service-level: refresh_live=False must not touch live QuickFile/Lunch Flow."""
    from app.services.finance.finance_overview_service import FinanceOverviewService

    called = {"qf_live": 0, "qf_refresh": 0, "lf_sync": 0, "ensure": 0}

    async def boom_qf_live(*_a, **_k):
        called["qf_live"] += 1
        raise AssertionError("fetch_live_reports must not run")

    async def boom_qf_refresh(*_a, **_k):
        called["qf_refresh"] += 1
        raise AssertionError("get_or_refresh_reports must not run")

    async def boom_lf(*_a, **_k):
        called["lf_sync"] += 1
        raise AssertionError("lunchflow sync must not run")

    async def boom_ensure(*_a, **_k):
        called["ensure"] += 1
        raise AssertionError("ensure_fresh must not run")

    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.QuickFileReportsService.fetch_live_reports",
        boom_qf_live,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.QuickFileReportsService.get_or_refresh_reports",
        boom_qf_refresh,
    )
    monkeypatch.setattr(
        "app.services.finance.lunchflow_sync_service.LunchFlowSyncService.sync_balances",
        boom_lf,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_live_refresh_service.ensure_fresh",
        boom_ensure,
    )

    class _EmptyResult:
        def all(self):
            return []

        def one(self):
            return (0, 0.0, None)

        def first(self):
            return None

    class _Db:
        async def scalars(self, _stmt):
            return _EmptyResult()

        async def scalar(self, _stmt):
            return None

        async def execute(self, _stmt):
            return _EmptyResult()

        async def get(self, *_a, **_k):
            return None

        async def commit(self):
            return None

        async def rollback(self):
            return None

        def add(self, *_a, **_k):
            return None

    async def empty_accounts(_db, **_kwargs):
        return []

    async def empty_liabilities(_db, **_kwargs):
        return []

    async def no_snap(_self, _db, _month):
        return None

    async def no_flow(_self, _db):
        return SimpleNamespace(income_gbp=0.0, spending_gbp=0.0)

    async def no_insights(_db, overview):
        return []

    async def no_period(_db, **_kwargs):
        return {
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

    monkeypatch.setattr(
        "app.services.finance.finance_overview_service.finance_accounts_service.list_accounts",
        empty_accounts,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_overview_service.finance_liabilities_service.list_liabilities",
        empty_liabilities,
    )
    monkeypatch.setattr(FinanceOverviewService, "personal_snapshot_for_month", no_snap)
    monkeypatch.setattr(FinanceOverviewService, "business_snapshot_for_month", no_snap)
    monkeypatch.setattr(FinanceOverviewService, "_open_banking_flow", no_flow)
    monkeypatch.setattr(
        "app.services.finance.finance_insights_service.finance_insights_service.refresh_for_overview",
        no_insights,
    )
    monkeypatch.setattr(
        "app.services.finance.finance_ledger_service.finance_ledger_service.period_flow_totals",
        no_period,
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

    overview = await FinanceOverviewService().get_overview(
        _Db(),  # type: ignore[arg-type]
        month="2026-08",
        refresh_live=False,
    )
    assert overview is not None
    assert called["qf_live"] == 0
    assert called["qf_refresh"] == 0
    assert called["lf_sync"] == 0
    assert called["ensure"] == 0


@pytest.mark.asyncio
async def test_overview_cache_invalidates_when_quickfile_reports_change(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """BS-only recode must bust Overview cache even if accounts are unchanged."""
    import json

    from app.db.models import AppSettingRow
    from app.db.session import SessionLocal
    from app.services.finance.finance_overview_cache_service import CACHE_VERSION

    assert CACHE_VERSION == "17"

    await login(client, "viewer", "viewer-pass")
    first = await client.get("/finance/overview")
    assert first.status_code == 200
    assert first.json().get("cached") is False

    cached = await client.get("/finance/overview")
    assert cached.json().get("cached") is True

    async with SessionLocal() as db:
        row = await db.get(AppSettingRow, "quickfile_reports")
        payload = {
            "synced_at": "2026-09-01T12:00:00+00:00",
            "profit_and_loss_month": None,
            "profit_and_loss_ytd": None,
            "balance_sheet": {
                "to_date": "2026-09-01",
                "fixed_assets_gbp": 37183.24,
                "current_assets_gbp": 10469.99,
                "current_liabilities_gbp": 43774.22,
                "long_term_liabilities_gbp": 0.0,
                "capital_and_reserves_gbp": 3879.01,
                "debtors_gbp": 7597.31,
                "creditors_gbp": 0.0,
                "vat_reserve_gbp": 0.47,
                "sections": [],
            },
        }
        encoded = json.dumps(payload)
        if row is None:
            db.add(AppSettingRow(key="quickfile_reports", value=encoded))
        else:
            row.value = encoded
        await db.commit()

    after = await client.get("/finance/overview")
    assert after.status_code == 200
    assert after.json().get("cached") is False
