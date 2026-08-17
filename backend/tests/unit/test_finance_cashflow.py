"""Cash-flow forecast seeding must not duplicate when the scope changes."""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from tests.conftest import login


async def _admin(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> str:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    return data["csrf_token"]


async def _stored_cashflow_count() -> int:
    from app.db.models import CashflowForecastRow
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        return int(
            await db.scalar(select(func.count()).select_from(CashflowForecastRow)) or 0
        )


@pytest.mark.asyncio
async def test_scoped_cashflow_does_not_reseed_duplicates(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    snapshot = await client.post(
        "/finance/snapshots/personal",
        json={
            "snapshot_date": month,
            "monthly_income_gbp": 4000,
            "monthly_spending_gbp": 1200,
            "household_bills_gbp": 800,
            "debt_repayments_gbp": 200,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert snapshot.status_code == 201

    personal_debt = await client.post(
        "/finance/liabilities",
        json={
            "scope": "personal",
            "name": "E2E-TEST-cashflow-personal-card",
            "debt_type": "credit_card",
            "balance_gbp": 900,
            "interest_rate_pct": 19.9,
            "minimum_payment_gbp": 35,
            "payment_day": 12,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert personal_debt.status_code == 201

    business_debt = await client.post(
        "/finance/liabilities",
        json={
            "scope": "business",
            "name": "E2E-TEST-cashflow-business-loan",
            "debt_type": "business_loan",
            "balance_gbp": 2500,
            "interest_rate_pct": 8.5,
            "minimum_payment_gbp": 120,
            "payment_day": 20,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert business_debt.status_code == 201

    personal = await client.get("/finance/cashflow?horizon=30&scope=personal")
    assert personal.status_code == 200
    personal_body = personal.json()
    assert personal_body["entries"]
    assert all(item["scope"] == "personal" for item in personal_body["entries"])
    assert any(item["entry_type"] == "income" for item in personal_body["entries"])
    assert any(
        "E2E-TEST-cashflow-personal-card" in item["label"]
        for item in personal_body["entries"]
    )
    after_personal = await _stored_cashflow_count()
    assert after_personal >= 3

    business = await client.get("/finance/cashflow?horizon=30&scope=business")
    assert business.status_code == 200
    business_body = business.json()
    assert all(item["scope"] == "business" for item in business_body["entries"])
    assert any(
        "E2E-TEST-cashflow-business-loan" in item["label"]
        for item in business_body["entries"]
    )
    assert await _stored_cashflow_count() == after_personal

    again = await client.get("/finance/cashflow?horizon=30&scope=personal")
    assert again.status_code == 200
    assert await _stored_cashflow_count() == after_personal

    combined = await client.get("/finance/cashflow?horizon=30")
    assert combined.status_code == 200
    labels = [item["label"] for item in combined.json()["entries"]]
    assert labels.count("Expected salary / income") == 1
    assert labels.count("Household bills") == 1
    assert sum("E2E-TEST-cashflow-personal-card" in label for label in labels) == 1
    assert sum("E2E-TEST-cashflow-business-loan" in label for label in labels) == 1
    assert await _stored_cashflow_count() == after_personal
