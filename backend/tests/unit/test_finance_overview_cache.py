"""Dashboard GET must return persisted figures without live or write-on-read work."""

from __future__ import annotations

from datetime import datetime, timezone

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
