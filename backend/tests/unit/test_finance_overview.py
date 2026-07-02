"""Unit tests for finance overview aggregation."""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_overview_aggregates_accounts(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    await login(client, "viewer", "viewer-pass")
    before = (await client.get("/finance/overview")).json()

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]

    await client.post(
        "/finance/accounts",
        json={
            "scope": "personal",
            "account_type": "current",
            "name": "Current",
            "balance_gbp": 2000,
        },
        headers={"X-CSRF-Token": csrf},
    )
    await client.post(
        "/finance/accounts",
        json={
            "scope": "business",
            "account_type": "current",
            "name": "Business current",
            "balance_gbp": 5000,
        },
        headers={"X-CSRF-Token": csrf},
    )
    await client.post(
        "/finance/snapshots/personal",
        json={
            "snapshot_date": datetime.now(timezone.utc).strftime("%Y-%m"),
            "monthly_income_gbp": 4000,
            "monthly_spending_gbp": 2500,
            "household_bills_gbp": 800,
            "debt_repayments_gbp": 200,
        },
        headers={"X-CSRF-Token": csrf},
    )

    await login(client, "viewer", "viewer-pass")
    response = await client.get("/finance/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["personal_bank_balance_gbp"] == before["personal_bank_balance_gbp"] + 2000
    assert body["business_bank_balance_gbp"] == before["business_bank_balance_gbp"] + 5000
    assert body["monthly_income_gbp"] == 4000
    assert body["cash_after_bills_gbp"] == round(body["personal_bank_balance_gbp"] - 800, 2)
