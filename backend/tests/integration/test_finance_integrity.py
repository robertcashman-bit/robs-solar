"""API tests for ledger import, scoped budgets, health, and sinking funds."""


import pytest
from httpx import AsyncClient

from tests.conftest import login


async def _admin(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> str:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    return data["csrf_token"]


def _headers(csrf: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf}


@pytest.mark.asyncio
async def test_import_preview_commit_and_list(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    rows = [
        {
            "posted_on": "2026-07-02",
            "amount_gbp": -20.5,
            "description": "NETFLIX",
            "account_name": "Current",
            "account_external_id": "acc-1",
            "external_id": "n-1",
            "scope": "personal",
        }
    ]
    preview = await client.post(
        "/finance/transactions/import/preview",
        json={"source": "manual", "rows": rows},
        headers=_headers(csrf),
    )
    assert preview.status_code == 200
    assert preview.json()["new_count"] == 1
    listed = await client.get("/finance/transactions")
    assert listed.json() == []

    committed = await client.post(
        "/finance/transactions/import/commit",
        json={"source": "manual", "rows": rows},
        headers=_headers(csrf),
    )
    assert committed.status_code == 200
    assert committed.json()["imported"] == 1
    again = await client.get("/finance/transactions")
    assert len(again.json()) == 1
    assert again.json()[0]["amount_gbp"] == -20.5

    duplicate = await client.post(
        "/finance/transactions/import/commit",
        json={"source": "manual", "rows": rows},
        headers=_headers(csrf),
    )
    assert duplicate.json()["imported"] == 0
    assert duplicate.json()["duplicate_count"] == 1


@pytest.mark.asyncio
async def test_separate_personal_and_business_history_budgets(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    personal_rows = [
        {
            "posted_on": f"2026-{month:02d}-05",
            "amount_gbp": -30,
            "description": "FOOD",
            "account_name": "Current",
            "account_external_id": "p1",
            "external_id": f"p-{month}",
            "scope": "personal",
            "category": "Food",
        }
        for month in range(1, 7)
    ]
    business_rows = [
        {
            "posted_on": f"2026-{month:02d}-05",
            "amount_gbp": -80,
            "description": "SOFTWARE",
            "account_name": "Business",
            "account_external_id": "b1",
            "external_id": f"b-{month}",
            "scope": "business",
            "category": "Software / IT",
        }
        for month in range(1, 7)
    ]
    await client.post(
        "/finance/transactions/import/commit",
        json={"source": "manual", "rows": personal_rows + business_rows},
        headers=_headers(csrf),
    )
    personal = await client.post(
        "/finance/budgets/from-history",
        json={"scope": "personal", "activate": True, "name": "Personal history"},
        headers=_headers(csrf),
    )
    assert personal.status_code == 201
    assert personal.json()["active_scope"] == "personal"
    assert all(line["scope"] == "personal" for line in personal.json()["lines"])
    business = await client.post(
        "/finance/budgets/from-history",
        json={"scope": "business", "activate": True, "name": "Business history"},
        headers=_headers(csrf),
    )
    assert business.status_code == 201
    assert business.json()["is_active"] is True
    still_personal = await client.get("/finance/budgets/active?scope=personal")
    assert still_personal.json()["id"] == personal.json()["id"]
    vs_personal = await client.get("/finance/budgets/vs-actual?month=2026-06&scope=personal")
    food = next(item for item in vs_personal.json()["lines"] if item["category"] == "Food")
    assert food["actual_source"] == "transactions"
    assert food["missing_actual"] is False
    assert food["actual_gbp"] == 30


@pytest.mark.asyncio
async def test_sinking_fund_and_health(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    created = await client.post(
        "/finance/sinking-funds",
        json={
            "scope": "personal",
            "name": "Car service",
            "target_gbp": 600,
            "due_on": "2027-08-16",
        },
        headers=_headers(csrf),
    )
    assert created.status_code == 200
    assert created.json()["monthly_contribution_gbp"] > 0
    assert created.json()["formula"].startswith("600")
    health = await client.get("/finance/health")
    assert health.status_code == 200
    assert health.json()["db_write"] is True
    heal = await client.post("/finance/health/self-heal", headers=_headers(csrf))
    assert heal.status_code == 200
    assert heal.json()["source_transactions_unchanged"] is True
    recon = await client.get("/finance/reconciliation")
    assert recon.status_code == 200
    assert recon.json()["auto_edited"] is False
