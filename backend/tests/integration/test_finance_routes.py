"""Integration tests for finance routes."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_finance_overview_empty(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/finance/overview")
    assert response.status_code == 200
    body = response.json()
    assert "net_worth_estimate_gbp" in body
    assert "insights" in body


@pytest.mark.asyncio
async def test_finance_account_crud(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]
    create = await client.post(
        "/finance/accounts",
        json={
            "scope": "personal",
            "account_type": "current",
            "name": "Main current",
            "balance_gbp": 1500,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert create.status_code == 201
    account_id = create.json()["id"]
    listing = await client.get("/finance/accounts?scope=personal")
    assert listing.status_code == 200
    assert any(a["id"] == account_id for a in listing.json())
    delete = await client.delete(
        f"/finance/accounts/{account_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert delete.status_code == 204


@pytest.mark.asyncio
async def test_liability_does_not_double_count_in_net_worth(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]
    before = (await client.get("/finance/overview")).json()["net_worth_estimate_gbp"]
    account = await client.post(
        "/finance/accounts",
        json={
            "scope": "personal",
            "account_type": "current",
            "name": "Calc current",
            "balance_gbp": 5000,
        },
        headers={"X-CSRF-Token": csrf},
    )
    card = await client.post(
        "/finance/accounts",
        json={
            "scope": "personal",
            "account_type": "credit_card",
            "name": "Calc card",
            "balance_gbp": 1000,
            "credit_limit_gbp": 3000,
        },
        headers={"X-CSRF-Token": csrf},
    )
    await client.post(
        "/finance/liabilities",
        json={
            "scope": "personal",
            "name": "Calc card",
            "debt_type": "credit_card",
            "balance_gbp": 1000,
            "interest_rate_pct": 22.9,
            "minimum_payment_gbp": 25,
            "account_id": card.json()["id"],
        },
        headers={"X-CSRF-Token": csrf},
    )
    after = (await client.get("/finance/overview")).json()
    assert after["available_credit_gbp"] >= 2000
    assert after["total_personal_debt_gbp"] >= 1000
    assert after["credit_card_balances_gbp"] >= 1000
    # +5000 cash -1000 card, counted once
    assert after["net_worth_estimate_gbp"] == pytest.approx(before + 4000, abs=0.01)
    await client.delete(f"/finance/accounts/{account.json()['id']}", headers={"X-CSRF-Token": csrf})
    await client.delete(f"/finance/accounts/{card.json()['id']}", headers={"X-CSRF-Token": csrf})


@pytest.mark.asyncio
async def test_credit_card_account_appears_on_debts(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]
    card = await client.post(
        "/finance/accounts",
        json={
            "scope": "personal",
            "account_type": "credit_card",
            "name": "MBNA card",
            "balance_gbp": 640,
            "interest_rate_pct": 22.9,
            "minimum_payment_gbp": 25,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert card.status_code == 201
    debts = await client.get("/finance/liabilities")
    assert debts.status_code == 200
    match = next(item for item in debts.json() if item["name"] == "MBNA card")
    assert match["balance_gbp"] == 640
    assert match["debt_type"] == "credit_card"
    assert match["account_id"] == card.json()["id"]
    strategy = await client.get("/finance/debts/strategy")
    assert strategy.status_code == 200
    assert strategy.json()["strategy"] != "none"
    await client.delete(f"/finance/accounts/{card.json()['id']}", headers={"X-CSRF-Token": csrf})
    leftover = await client.get("/finance/liabilities")
    assert not any(item["name"] == "MBNA card" for item in leftover.json())

