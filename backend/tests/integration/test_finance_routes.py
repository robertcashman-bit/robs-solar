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
