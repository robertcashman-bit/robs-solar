"""Integration tests for named budget plans."""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from tests.conftest import login


async def _admin(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> str:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    return data["csrf_token"]


@pytest.mark.asyncio
async def test_suggested_budgets_and_activate_persist(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    await client.post(
        "/finance/snapshots/personal",
        json={
            "snapshot_date": datetime.now(timezone.utc).strftime("%Y-%m"),
            "monthly_income_gbp": 4500,
            "monthly_spending_gbp": 2200,
            "household_bills_gbp": 950,
            "debt_repayments_gbp": 180,
        },
        headers={"X-CSRF-Token": csrf},
    )
    suggestions = await client.get("/finance/budgets/suggestions")
    assert suggestions.status_code == 200
    body = suggestions.json()
    assert len(body["options"]) == 3
    assert {item["style"] for item in body["options"]} == {
        "stabilise",
        "balanced",
        "debt_attack",
    }

    created = await client.post(
        "/finance/budgets/from-suggestion",
        json={"style": "balanced", "name": "My Balanced Budget"},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201
    plan = created.json()
    assert plan["name"] == "My Balanced Budget"
    assert plan["lines"]
    first_amount = plan["lines"][0]["amount_gbp"]
    plan["lines"][0]["amount_gbp"] = first_amount + 25

    updated = await client.put(
        f"/finance/budgets/{plan['id']}",
        json={"name": "My Balanced Budget", "lines": plan["lines"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert updated.status_code == 200
    assert updated.json()["lines"][0]["amount_gbp"] == first_amount + 25

    activated = await client.post(
        f"/finance/budgets/{plan['id']}/activate",
        headers={"X-CSRF-Token": csrf},
    )
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True

    listing = await client.get("/finance/budgets")
    assert listing.status_code == 200
    saved = next(item for item in listing.json() if item["id"] == plan["id"])
    assert saved["is_active"] is True
    assert saved["name"] == "My Balanced Budget"

    overview = await client.get("/finance/overview")
    assert overview.status_code == 200
    assert overview.json()["active_budget"]["id"] == plan["id"]

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    category = plan["lines"][0]["category"]
    scope = plan["lines"][0]["scope"]
    unmatched = await client.get(f"/finance/budgets/vs-actual?month={month}")
    assert unmatched.status_code == 200
    unmatched_line = next(
        item
        for item in unmatched.json()["lines"]
        if item["category"] == category and item["scope"] == scope
    )
    assert unmatched_line["missing_actual"] is True
    assert unmatched_line["actual_gbp"] is None
    assert unmatched_line["variance_gbp"] is None

    starter = await client.post(
        "/finance/budget/starter",
        json={"month": month, "scope": "personal"},
        headers={"X-CSRF-Token": csrf},
    )
    assert starter.status_code == 200
    starter_lines = starter.json()
    if starter_lines:
        assert starter_lines[0]["actual_recorded"] is False
        assert starter_lines[0]["actual_gbp"] is None

    recorded = await client.put(
        "/finance/budget",
        json={
            "scope": scope,
            "month": month,
            "category": category,
            "budgeted_gbp": plan["lines"][0]["amount_gbp"],
            "actual_gbp": 12.5,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert recorded.status_code == 200
    vs_actual = await client.get(f"/finance/budgets/vs-actual?month={month}")
    assert vs_actual.status_code == 200
    match = next(
        item
        for item in vs_actual.json()["lines"]
        if item["category"] == category and item["scope"] == scope
    )
    assert match["actual_gbp"] == 12.5
    assert match["missing_actual"] is False
    assert vs_actual.json()["available"] is True
    assert vs_actual.json()["has_actuals"] is True

    extra = await client.put(
        "/finance/budget",
        json={
            "scope": "personal",
            "month": month,
            "category": "Unplanned tesla",
            "budgeted_gbp": 0,
            "actual_gbp": 359.47,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert extra.status_code == 200
    with_unbudgeted = await client.get(f"/finance/budgets/vs-actual?month={month}")
    assert with_unbudgeted.status_code == 200
    unbudgeted = with_unbudgeted.json()["unbudgeted_actuals"]
    assert any(item["category"] == "Unplanned tesla" for item in unbudgeted)
    assert with_unbudgeted.json()["actual_total_gbp"] >= 359.47

    reports = await client.get(f"/finance/reports?month={month}")
    assert reports.status_code == 200
    report_body = reports.json()
    assert report_body["active_budget"]["id"] == plan["id"]
    assert report_body["active_budget"]["income_gbp"] > 0
    assert report_body["budget_vs_actual"]["available"] is True
    assert any(
        item["category"] == "Unplanned tesla"
        for item in report_body["budget_vs_actual"]["unbudgeted_actuals"]
    )

    batch = await client.put(
        "/finance/budget/batch",
        json={
            "lines": [
                {
                    "scope": scope,
                    "month": month,
                    "category": category,
                    "budgeted_gbp": plan["lines"][0]["amount_gbp"],
                    "actual_gbp": 40,
                }
            ]
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert batch.status_code == 200
    assert batch.json()[0]["actual_gbp"] == 40


@pytest.mark.asyncio
async def test_duplicate_and_custom_budget(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    created = await client.post(
        "/finance/budgets",
        json={
            "name": "Blank custom",
            "style": "custom",
            "income_gbp": 3000,
            "lines": [
                {
                    "scope": "personal",
                    "category": "Food",
                    "amount_gbp": 350,
                    "source": "user",
                    "is_custom": True,
                }
            ],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201
    plan_id = created.json()["id"]
    duplicate = await client.post(
        f"/finance/budgets/{plan_id}/duplicate",
        headers={"X-CSRF-Token": csrf},
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] != plan_id
    assert "copy" in duplicate.json()["name"].lower()


async def _set_lunchflow_income(income_gbp: float, spending_gbp: float = 0.0) -> None:
    from app.db.session import SessionLocal
    from app.services.lunchflow_settings_service import lunchflow_settings_service

    async with SessionLocal() as db:
        await lunchflow_settings_service.set_monthly_flow(db, income_gbp, spending_gbp)


@pytest.mark.asyncio
async def test_suggestions_use_open_banking_income_when_snapshot_missing(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _admin(client, monkeypatch)
    await _set_lunchflow_income(4252.60, 4344.97)

    suggestions = await client.get("/finance/budgets/suggestions")
    assert suggestions.status_code == 200
    body = suggestions.json()
    assert body["personal_income_known"] is True
    assert body["income_gbp"] == 4252.6
    assert {item["style"] for item in body["options"]} == {
        "stabilise",
        "balanced",
        "debt_attack",
    }
    assert all(item["income_gbp"] == 4252.6 for item in body["options"])
    assert not any("income" in gap["message"].lower() for gap in body["gaps"])


@pytest.mark.asyncio
async def test_overview_activates_recommended_budget_from_live_income(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _admin(client, monkeypatch)
    await _set_lunchflow_income(4252.60, 1000)

    stored = await client.get("/finance/overview")
    assert stored.status_code == 200
    assert stored.json()["active_budget"] is None

    first = await client.get("/finance/overview?live=1")
    assert first.status_code == 200
    budget = first.json()["active_budget"]
    assert budget is not None
    assert budget["income_gbp"] == 4252.6
    assert budget["style"] in {"stabilise", "balanced", "debt_attack"}
    assert budget["monthly_total_gbp"] > 0

    second = await client.get("/finance/overview")
    assert second.json()["active_budget"]["id"] == budget["id"]
    listing = await client.get("/finance/budgets")
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["is_active"] is True
    assert listing.json()[0]["origin"] == "suggested"

    reports = await client.get("/finance/reports")
    assert reports.status_code == 200
    assert reports.json()["active_budget"]["id"] == budget["id"]
    assert reports.json()["budget_vs_actual"]["available"] is True
    assert all(
        line["missing_actual"] is True for line in reports.json()["budget_vs_actual"]["lines"]
    )


@pytest.mark.asyncio
async def test_live_refresh_does_not_override_saved_plans(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    created = await client.post(
        "/finance/budgets",
        json={
            "name": "Keep this custom",
            "style": "custom",
            "income_gbp": 3000,
            "lines": [
                {
                    "scope": "personal",
                    "category": "Food",
                    "amount_gbp": 200,
                    "source": "user",
                    "is_custom": True,
                }
            ],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201
    await _set_lunchflow_income(4252.60)

    overview = await client.get("/finance/overview")
    assert overview.status_code == 200
    assert overview.json()["active_budget"] is None
    listing = await client.get("/finance/budgets")
    assert [item["name"] for item in listing.json()] == ["Keep this custom"]


@pytest.mark.asyncio
async def test_snapshot_only_does_not_auto_create_a_budget(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    await client.post(
        "/finance/snapshots/personal",
        json={
            "snapshot_date": datetime.now(timezone.utc).strftime("%Y-%m"),
            "monthly_income_gbp": 4500,
            "monthly_spending_gbp": 2200,
            "household_bills_gbp": 950,
            "debt_repayments_gbp": 180,
        },
        headers={"X-CSRF-Token": csrf},
    )
    suggestions = await client.get("/finance/budgets/suggestions")
    assert suggestions.status_code == 200
    assert suggestions.json()["income_gbp"] == 4500
    listing = await client.get("/finance/budgets")
    assert listing.json() == []


@pytest.mark.asyncio
async def test_from_suggestion_can_activate_in_one_step(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    await client.post(
        "/finance/snapshots/personal",
        json={
            "snapshot_date": datetime.now(timezone.utc).strftime("%Y-%m"),
            "monthly_income_gbp": 4500,
            "monthly_spending_gbp": 2200,
            "household_bills_gbp": 950,
            "debt_repayments_gbp": 180,
        },
        headers={"X-CSRF-Token": csrf},
    )
    created = await client.post(
        "/finance/budgets/from-suggestion",
        json={"style": "debt_attack", "activate": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201
    assert created.json()["is_active"] is True
    assert created.json()["style"] == "debt_attack"
    overview = await client.get("/finance/overview")
    assert overview.json()["active_budget"]["id"] == created.json()["id"]
