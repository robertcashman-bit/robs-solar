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


@pytest.mark.asyncio
async def test_overview_ignores_older_month_snapshots(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import delete

    from app.config import settings
    from app.db.models import BusinessFinanceSnapshotRow, PersonalFinanceSnapshotRow
    from app.db.session import SessionLocal

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]
    async with SessionLocal() as db:
        await db.execute(delete(PersonalFinanceSnapshotRow))
        await db.execute(delete(BusinessFinanceSnapshotRow))
        await db.commit()

    personal = await client.post(
        "/finance/snapshots/personal",
        json={
            "snapshot_date": "2009-12",
            "monthly_income_gbp": 7777,
            "monthly_spending_gbp": 100,
            "household_bills_gbp": 50,
            "debt_repayments_gbp": 10,
        },
        headers={"X-CSRF-Token": csrf},
    )
    business = await client.post(
        "/finance/snapshots/business",
        json={
            "snapshot_date": "2009-12",
            "turnover_gbp": 9000,
            "expenses_gbp": 100,
            "vat_reserve_gbp": 8888,
            "corp_tax_reserve_gbp": 777,
            "debtors_gbp": 666,
            "creditors_gbp": 10,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert personal.status_code == 201
    assert business.status_code == 201

    after = (await client.get("/finance/overview")).json()
    assert after["monthly_income_gbp"] == 0
    assert after["monthly_surplus_gbp"] == 0
    assert after["vat_reserve_gbp"] != 8888

    scoped = (await client.get("/finance/overview?month=2009-12")).json()
    assert scoped["monthly_income_gbp"] == 7777
    assert scoped["vat_reserve_gbp"] == 8888


async def _clear_monthly_flow_inputs() -> None:
    from sqlalchemy import delete

    from app.db.models import CashflowForecastRow, MonthlyBudgetRow, PersonalFinanceSnapshotRow
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        await db.execute(delete(PersonalFinanceSnapshotRow))
        await db.execute(delete(CashflowForecastRow))
        await db.execute(delete(MonthlyBudgetRow))
        await db.commit()


@pytest.mark.asyncio
async def test_overview_uses_cashflow_when_snapshot_is_empty(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]
    await _clear_monthly_flow_inputs()
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    created = await client.post(
        "/finance/cashflow",
        json={
            "scope": "personal",
            "forecast_date": f"{month}-10",
            "horizon_days": 30,
            "entry_type": "income",
            "label": "Salary",
            "amount_gbp": 2600,
            "is_confirmed": True,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201
    bill = await client.post(
        "/finance/cashflow",
        json={
            "scope": "personal",
            "forecast_date": f"{month}-12",
            "horizon_days": 30,
            "entry_type": "bill",
            "label": "Rent",
            "amount_gbp": -900,
            "is_confirmed": True,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert bill.status_code == 201

    body = (await client.get("/finance/overview")).json()
    assert body["monthly_flow_source"] == "cashflow"
    assert body["monthly_income_gbp"] == 2600
    assert body["monthly_spending_gbp"] == 900
    assert body["household_bills_gbp"] == 900


@pytest.mark.asyncio
async def test_overview_uses_budget_when_no_snapshot_or_cashflow(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]
    await _clear_monthly_flow_inputs()
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    line = await client.put(
        "/finance/budget",
        json={
            "scope": "personal",
            "month": month,
            "category": "Groceries",
            "budgeted_gbp": 400,
            "actual_gbp": 350,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert line.status_code == 200

    body = (await client.get("/finance/overview")).json()
    assert body["monthly_flow_source"] == "budget"
    assert body["monthly_spending_gbp"] == 350


@pytest.mark.asyncio
async def test_overview_uses_truelayer_flow_when_lunchflow_empty(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings
    from app.db.session import SessionLocal
    from app.services.truelayer_settings_service import truelayer_settings_service

    monkeypatch.setattr(settings, "read_only", False)
    await login(client, "admin", "admin-pass")
    await _clear_monthly_flow_inputs()
    async with SessionLocal() as db:
        await truelayer_settings_service.set_monthly_flow(db, 2750, 880)

    body = (await client.get("/finance/overview")).json()
    assert body["monthly_flow_source"] == "open_banking"
    assert body["monthly_income_gbp"] == 2750
    assert body["monthly_spending_gbp"] == 880


@pytest.mark.asyncio
async def test_historical_reports_do_not_overwrite_stored_debt(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings
    from app.db.models import FinancePositionSnapshotRow
    from app.db.session import SessionLocal

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]
    async with SessionLocal() as db:
        db.add(
            FinancePositionSnapshotRow(
                month="2026-01",
                total_debt_gbp=5000,
                personal_debt_gbp=5000,
                business_debt_gbp=0,
                net_worth_gbp=12000,
                cash_available_gbp=2000,
                recorded_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

    added = await client.post(
        "/finance/liabilities",
        json={
            "scope": "personal",
            "name": "Live card",
            "debt_type": "credit_card",
            "balance_gbp": 800,
            "interest_rate_pct": 19.9,
            "minimum_payment_gbp": 25,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert added.status_code == 201

    current = (await client.get("/finance/reports")).json()
    assert current["total_debt_gbp"] >= 800

    historical = (await client.get("/finance/reports?month=2026-01")).json()
    assert historical["total_debt_gbp"] == 5000
    assert historical["net_worth_gbp"] == 12000

    await client.get("/finance/overview?month=2026-01")
    after = (await client.get("/finance/reports?month=2026-01")).json()
    assert after["total_debt_gbp"] == 5000
    assert after["net_worth_gbp"] == 12000


@pytest.mark.asyncio
async def test_historical_reports_without_position_do_not_use_live_totals(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings
    from app.db.models import FinancePositionSnapshotRow
    from app.db.session import SessionLocal

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]
    added = await client.post(
        "/finance/liabilities",
        json={
            "scope": "personal",
            "name": "Live-only card",
            "debt_type": "credit_card",
            "balance_gbp": 800,
            "interest_rate_pct": 19.9,
            "minimum_payment_gbp": 25,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert added.status_code == 201

    missing = (await client.get("/finance/reports?month=1999-01")).json()
    assert missing["total_debt_gbp"] is None
    assert missing["net_worth_gbp"] is None
    assert missing["debt_reduction_available"] is False
    assert missing["debt_reduction_gbp"] is None

    current = (await client.get("/finance/reports")).json()
    assert current["total_debt_gbp"] >= 800

    async with SessionLocal() as db:
        db.add(
            FinancePositionSnapshotRow(
                month="2026-01",
                total_debt_gbp=5000,
                personal_debt_gbp=5000,
                business_debt_gbp=0,
                net_worth_gbp=12000,
                cash_available_gbp=2000,
                recorded_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            FinancePositionSnapshotRow(
                month="2026-03",
                total_debt_gbp=3000,
                personal_debt_gbp=3000,
                business_debt_gbp=0,
                net_worth_gbp=14000,
                cash_available_gbp=2500,
                recorded_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

    gap = (await client.get("/finance/reports?month=2026-02")).json()
    assert gap["total_debt_gbp"] is None
    assert gap["net_worth_gbp"] is None
    assert gap["debt_reduction_available"] is False

    march = (await client.get("/finance/reports?month=2026-03")).json()
    assert march["total_debt_gbp"] == 3000
    assert march["net_worth_gbp"] == 14000
    assert march["debt_reduction_available"] is True
    assert march["debt_reduction_gbp"] == 2000
    assert march["previous_month_debt_gbp"] == 5000
