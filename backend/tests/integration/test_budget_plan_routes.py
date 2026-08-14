"""Integration tests for persisted budget plans."""

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.db.models import FinanceBudgetItemRow, FinanceBudgetPlanRow
from app.db.session import SessionLocal
from tests.conftest import login


async def _wipe_budgets() -> None:
    async with SessionLocal() as db:
        await db.execute(delete(FinanceBudgetItemRow))
        await db.execute(delete(FinanceBudgetPlanRow))
        await db.commit()


@pytest.mark.asyncio
async def test_suggestions_do_not_invent_income(client: AsyncClient) -> None:
    await _wipe_budgets()
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/finance/budget-plans/suggestions")
    assert response.status_code == 200
    body = response.json()
    assert "suggestions" in body
    strategies = {row["strategy"] for row in body["suggestions"]}
    assert strategies == {"stabilise", "balanced", "debt_attack", "custom"}
    for row in body["suggestions"]:
        assert row["totals_consolidated"]["income_gbp"] >= 0
        if not row["totals_consolidated"]["income_complete"]:
            assert row["totals_consolidated"]["surplus_gbp"] is None


@pytest.mark.asyncio
async def test_budget_plan_save_activate_duplicate_delete(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    await _wipe_budgets()
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]
    headers = {"X-CSRF-Token": csrf}

    created = await client.post(
        "/finance/budget-plans",
        json={
            "name": "E2E Balanced",
            "strategy": "balanced",
            "activate": True,
            "source_fingerprint": "abc",
            "items": [
                {
                    "key": "personal:income:user:1:pay",
                    "scope": "personal",
                    "kind": "income",
                    "category": "Pay",
                    "amount_gbp": 3000,
                    "source": "user_entered",
                },
                {
                    "key": "personal:essential:user:1:bills",
                    "scope": "personal",
                    "kind": "essential",
                    "category": "Bills",
                    "amount_gbp": 900,
                    "source": "user_entered",
                },
            ],
        },
        headers=headers,
    )
    assert created.status_code == 201
    plan = created.json()
    assert plan["is_active"] is True
    assert plan["totals_consolidated"]["income_gbp"] == 3000
    assert plan["totals_consolidated"]["surplus_gbp"] == 2100
    plan_id = plan["id"]

    updated = await client.put(
        f"/finance/budget-plans/{plan_id}",
        json={
            "items": [
                {
                    "key": "personal:income:user:1:pay",
                    "scope": "personal",
                    "kind": "income",
                    "category": "Pay",
                    "amount_gbp": 3000,
                    "source": "user_override",
                    "is_user_override": True,
                },
                {
                    "key": "personal:essential:user:1:bills",
                    "scope": "personal",
                    "kind": "essential",
                    "category": "Bills",
                    "amount_gbp": 1100,
                    "source": "user_override",
                    "is_user_override": True,
                },
            ]
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["totals_consolidated"]["surplus_gbp"] == 1900

    loaded = await client.get(f"/finance/budget-plans/{plan_id}")
    assert loaded.status_code == 200
    assert loaded.json()["totals_consolidated"]["essential_gbp"] == 1100

    active = await client.get("/finance/budget-plans/active")
    assert active.status_code == 200
    assert active.json()["id"] == plan_id

    copied = await client.post(
        f"/finance/budget-plans/{plan_id}/duplicate",
        json={"name": "E2E Balanced copy"},
        headers=headers,
    )
    assert copied.status_code == 200
    copy = copied.json()
    assert copy["id"] != plan_id
    assert copy["is_active"] is False
    assert copy["name"] == "E2E Balanced copy"
    assert copy["totals_consolidated"]["essential_gbp"] == 1100

    blocked = await client.delete(f"/finance/budget-plans/{plan_id}", headers=headers)
    assert blocked.status_code == 409

    await client.post(f"/finance/budget-plans/{plan_id}/deactivate", headers=headers)
    deleted = await client.delete(f"/finance/budget-plans/{plan_id}", headers=headers)
    assert deleted.status_code == 204
    gone = await client.get(f"/finance/budget-plans/{plan_id}")
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_deficit_plan_saves_without_inventing_income(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    await _wipe_budgets()
    data = await login(client, "admin", "admin-pass")
    headers = {"X-CSRF-Token": data["csrf_token"]}
    created = await client.post(
        "/finance/budget-plans",
        json={
            "name": "Deficit plan",
            "strategy": "custom",
            "items": [
                {
                    "key": "personal:income:user:1:pay",
                    "scope": "personal",
                    "kind": "income",
                    "category": "Pay",
                    "amount_gbp": 400,
                    "source": "user_entered",
                },
                {
                    "key": "personal:essential:user:1:bills",
                    "scope": "personal",
                    "kind": "essential",
                    "category": "Bills",
                    "amount_gbp": 900,
                    "source": "user_entered",
                },
            ],
        },
        headers=headers,
    )
    assert created.status_code == 201
    totals = created.json()["totals_consolidated"]
    assert totals["is_deficit"] is True
    assert totals["surplus_gbp"] == -500
    assert totals["income_gbp"] == 400


@pytest.mark.asyncio
async def test_missing_amount_is_not_coerced_to_zero(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    await _wipe_budgets()
    data = await login(client, "admin", "admin-pass")
    headers = {"X-CSRF-Token": data["csrf_token"]}
    created = await client.post(
        "/finance/budget-plans",
        json={
            "name": "Missing income",
            "strategy": "custom",
            "items": [
                {
                    "key": "personal:income:user:1:pay",
                    "scope": "personal",
                    "kind": "income",
                    "category": "Pay",
                    "amount_gbp": None,
                    "is_missing": True,
                    "source": "user_entered",
                },
                {
                    "key": "personal:essential:user:1:bills",
                    "scope": "personal",
                    "kind": "essential",
                    "category": "Bills",
                    "amount_gbp": 200,
                    "source": "user_entered",
                },
            ],
        },
        headers=headers,
    )
    assert created.status_code == 201
    body = created.json()
    income = next(i for i in body["items"] if i["kind"] == "income")
    assert income["amount_gbp"] is None
    assert income["is_missing"] is True
    assert body["totals_consolidated"]["surplus_gbp"] is None
    assert body["totals_consolidated"]["income_complete"] is False
