"""Integration-style reconciliation tests for finance calculations and reports."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from tests.conftest import login


async def _admin(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> str:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    return data["csrf_token"]


@pytest.mark.asyncio
async def test_net_worth_does_not_double_count_liability(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    before = (await client.get("/finance/overview")).json()
    before_reports = (await client.get("/finance/reports")).json()

    account = await client.post(
        "/finance/accounts",
        json={
            "scope": "personal",
            "account_type": "current",
            "name": "Reconcile current",
            "balance_gbp": 1000,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert account.status_code == 201

    liability = await client.post(
        "/finance/liabilities",
        json={
            "scope": "personal",
            "name": "Reconcile card",
            "debt_type": "credit_card",
            "balance_gbp": 400,
            "interest_rate_pct": 19.9,
            "minimum_payment_gbp": 25,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert liability.status_code == 201

    after = (await client.get("/finance/overview")).json()
    assert after["personal_bank_balance_gbp"] == before["personal_bank_balance_gbp"] + 1000
    assert after["total_personal_debt_gbp"] == before["total_personal_debt_gbp"] + 400
    assert after["credit_card_balances_gbp"] == before["credit_card_balances_gbp"] + 400
    assert after["net_worth_estimate_gbp"] == round(
        before["net_worth_estimate_gbp"] + 1000 - 400, 2
    )

    reports = (await client.get("/finance/reports")).json()
    assert reports["net_worth_gbp"] == after["net_worth_estimate_gbp"]
    assert reports["total_debt_gbp"] == round(before_reports["total_debt_gbp"] + 400, 2)


@pytest.mark.asyncio
async def test_reports_debt_reduction_is_unavailable_without_history(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _admin(client, monkeypatch)
    reports = (await client.get("/finance/reports?month=1999-01")).json()
    assert reports["month"] == "1999-01"
    assert reports["debt_reduction_gbp"] is None
    assert reports["total_debt_gbp"] is None
    assert reports["net_worth_gbp"] is None
    assert reports["debt_reduction_available"] is False
    assert reports["energy_savings_gbp"] == 0
    assert reports["energy_savings_vs_forecast"] == ""
    assert reports["personal_snapshot"] is None
    assert reports["business_snapshot"] is None


@pytest.mark.asyncio
async def test_reports_filters_snapshots_by_month(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    jan = await client.post(
        "/finance/snapshots/personal",
        json={
            "snapshot_date": "2011-01",
            "monthly_income_gbp": 1111,
            "monthly_spending_gbp": 100,
            "household_bills_gbp": 50,
            "debt_repayments_gbp": 10,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert jan.status_code == 201
    assert jan.json()["snapshot_date"] == "2011-01-01"
    jun = await client.post(
        "/finance/snapshots/personal",
        json={
            "snapshot_date": "2011-06-15",
            "monthly_income_gbp": 2222,
            "monthly_spending_gbp": 200,
            "household_bills_gbp": 80,
            "debt_repayments_gbp": 20,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert jun.status_code == 201

    january = (await client.get("/finance/reports?month=2011-01")).json()
    june = (await client.get("/finance/reports?month=2011-06")).json()
    assert january["personal_snapshot"]["monthly_income_gbp"] == 1111
    assert june["personal_snapshot"]["monthly_income_gbp"] == 2222


@pytest.mark.asyncio
async def test_reports_finds_snapshot_older_than_recent_list(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.db.models import PersonalFinanceSnapshotRow
    from app.db.session import SessionLocal

    await _admin(client, monkeypatch)
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        db.add(
            PersonalFinanceSnapshotRow(
                snapshot_date="2010-01-01",
                monthly_income_gbp=1010,
                monthly_spending_gbp=10,
                household_bills_gbp=10,
                debt_repayments_gbp=10,
                surplus_deficit_gbp=990,
                notes="",
                breakdown_json="{}",
                created_at=now - timedelta(days=4000),
            )
        )
        for index in range(25):
            year = 2014 + (index // 12)
            month = (index % 12) + 1
            db.add(
                PersonalFinanceSnapshotRow(
                    snapshot_date=f"{year}-{month:02d}-01",
                    monthly_income_gbp=3000 + index,
                    monthly_spending_gbp=10,
                    household_bills_gbp=10,
                    debt_repayments_gbp=10,
                    surplus_deficit_gbp=2980 + index,
                    notes="",
                    breakdown_json="{}",
                    created_at=now - timedelta(days=25 - index),
                )
            )
        await db.commit()

    listed = (await client.get("/finance/snapshots/personal")).json()
    assert len(listed) == 12
    assert all(not item["snapshot_date"].startswith("2010-01") for item in listed)

    report = (await client.get("/finance/reports?month=2010-01")).json()
    assert report["personal_snapshot"] is not None
    assert report["personal_snapshot"]["monthly_income_gbp"] == 1010


@pytest.mark.asyncio
async def test_reports_uses_newest_same_month_snapshot(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    first = await client.post(
        "/finance/snapshots/personal",
        json={
            "snapshot_date": "2013-04",
            "monthly_income_gbp": 100,
            "monthly_spending_gbp": 10,
            "household_bills_gbp": 10,
            "debt_repayments_gbp": 10,
        },
        headers={"X-CSRF-Token": csrf},
    )
    second = await client.post(
        "/finance/snapshots/personal",
        json={
            "snapshot_date": "2013-04",
            "monthly_income_gbp": 200,
            "monthly_spending_gbp": 20,
            "household_bills_gbp": 20,
            "debt_repayments_gbp": 20,
        },
        headers={"X-CSRF-Token": csrf},
    )
    biz_first = await client.post(
        "/finance/snapshots/business",
        json={
            "snapshot_date": "2013-04",
            "turnover_gbp": 1000,
            "expenses_gbp": 100,
            "vat_reserve_gbp": 10,
            "corp_tax_reserve_gbp": 10,
            "debtors_gbp": 10,
            "creditors_gbp": 10,
        },
        headers={"X-CSRF-Token": csrf},
    )
    biz_second = await client.post(
        "/finance/snapshots/business",
        json={
            "snapshot_date": "2013-04",
            "turnover_gbp": 2000,
            "expenses_gbp": 200,
            "vat_reserve_gbp": 20,
            "corp_tax_reserve_gbp": 20,
            "debtors_gbp": 20,
            "creditors_gbp": 20,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert biz_first.status_code == 201
    assert biz_second.status_code == 201

    report = (await client.get("/finance/reports?month=2013-04")).json()
    assert report["personal_snapshot"]["monthly_income_gbp"] == 200
    assert report["business_snapshot"]["turnover_gbp"] == 2000


@pytest.mark.asyncio
async def test_finance_write_requires_csrf(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    await login(client, "admin", "admin-pass")
    response = await client.post(
        "/finance/accounts",
        json={
            "scope": "personal",
            "account_type": "current",
            "name": "No CSRF",
            "balance_gbp": 1,
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_liability_and_budget_crud(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    created = await client.post(
        "/finance/liabilities",
        json={
            "scope": "personal",
            "name": "CRUD card",
            "debt_type": "credit_card",
            "balance_gbp": 120,
            "interest_rate_pct": 12,
            "minimum_payment_gbp": 15,
            "overpayment_gbp": 5,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201
    debt_id = created.json()["id"]
    updated = await client.put(
        f"/finance/liabilities/{debt_id}",
        json={"balance_gbp": 90, "minimum_payment_gbp": 20},
        headers={"X-CSRF-Token": csrf},
    )
    assert updated.status_code == 200
    assert updated.json()["balance_gbp"] == 90
    assert updated.json()["minimum_payment_gbp"] == 20

    budget = await client.put(
        "/finance/budget",
        json={
            "scope": "personal",
            "month": "2012-03",
            "category": "Groceries",
            "budgeted_gbp": 200,
            "actual_gbp": 0,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert budget.status_code == 200
    line_id = budget.json()["id"]
    patched = await client.patch(
        f"/finance/budget/{line_id}",
        json={"actual_gbp": 45},
        headers={"X-CSRF-Token": csrf},
    )
    assert patched.status_code == 200
    assert patched.json()["actual_gbp"] == 45
    assert patched.json()["remaining_gbp"] == 155

    listed = (await client.get("/finance/budget?month=2012-03&scope=personal")).json()
    match = next(item for item in listed if item["id"] == line_id)
    assert match["remaining_gbp"] == 155

    deleted = await client.delete(
        f"/finance/liabilities/{debt_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert deleted.status_code == 204
    remaining = (await client.get("/finance/liabilities")).json()
    assert all(item["id"] != debt_id for item in remaining)


@pytest.mark.asyncio
async def test_dismissed_insight_is_not_recreated(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import delete

    from app.db.models import FinanceInsightRow
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        await db.execute(delete(FinanceInsightRow))
        await db.commit()

    csrf = await _admin(client, monkeypatch)
    snap = await client.post(
        "/finance/snapshots/personal",
        json={
            "snapshot_date": datetime.now(timezone.utc).strftime("%Y-%m"),
            "monthly_income_gbp": 100,
            "monthly_spending_gbp": 50,
            "household_bills_gbp": 999999,
            "debt_repayments_gbp": 0,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert snap.status_code == 201

    overview = (await client.get("/finance/overview")).json()
    tight = [
        item
        for item in overview["insights"]
        if item["title"] == "Personal cash may be tight after expected bills"
    ]
    assert tight
    dismiss = await client.post(
        f"/finance/insights/{tight[0]['id']}/dismiss",
        headers={"X-CSRF-Token": csrf},
    )
    assert dismiss.status_code == 204

    again = (await client.get("/finance/overview")).json()
    assert all(
        item["title"] != "Personal cash may be tight after expected bills"
        for item in again["insights"]
    )
