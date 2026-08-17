import os
import tempfile
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

_TEST_DB_PATH = Path(tempfile.gettempdir()) / f"robs_solar_pytest_{uuid.uuid4().hex}.db"

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_PATH}"
os.environ["FINANCE_KEEP_SQLITE"] = "true"
os.environ.setdefault("APP_ENV", "test")
os.environ["READ_ONLY"] = "true"
os.environ["ENABLE_LIVE_WRITES"] = "false"
os.environ["SUNSYNK_ENABLE_UNVERIFIED_WRITES"] = "false"
os.environ["ADAPTER_MODE"] = "simulator"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-pass"
os.environ["VIEWER_USERNAME"] = "viewer"
os.environ["VIEWER_PASSWORD"] = "viewer-pass"
os.environ.setdefault("METRICS_SAMPLER_ENABLED", "false")
os.environ.setdefault("AI_ENABLED", "false")
os.environ["QUICKFILE_ACCOUNT_NUMBER"] = ""
os.environ["QUICKFILE_API_KEY"] = ""
os.environ["QUICKFILE_APPLICATION_ID"] = ""
os.environ["TRUELAYER_CLIENT_ID"] = ""
os.environ["TRUELAYER_CLIENT_SECRET"] = ""
os.environ["LUNCHFLOW_API_KEY"] = ""
os.environ["LUNCH_FLOW_API_KEY"] = ""
os.environ["CRON_SECRET"] = ""
os.environ["TESLA_REFRESH_TOKEN"] = ""
os.environ["OIDC_ENABLED"] = "false"

from app.db.session import init_db  # noqa: E402
from app.main import app  # noqa: E402


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(_TEST_DB_PATH) + suffix)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


@pytest_asyncio.fixture(autouse=True)
async def setup_db() -> AsyncGenerator[None, None]:
    await init_db()
    yield


@pytest_asyncio.fixture(autouse=True)
async def reset_finance_rows(setup_db: None) -> AsyncGenerator[None, None]:
    from sqlalchemy import delete

    from app.db.models import (
        BusinessFinanceSnapshotRow,
        CashflowForecastRow,
        FinanceAccountRow,
        FinanceBackupSnapshotRow,
        FinanceBudgetPlanLineRow,
        FinanceBudgetPlanRow,
        FinanceChangeAuditRow,
        FinanceHealthEventRow,
        FinanceImportBatchRow,
        FinanceInsightRow,
        FinanceLiabilityRow,
        FinanceOverviewCacheRow,
        FinancePositionSnapshotRow,
        FinanceRecurringRuleRow,
        FinanceSinkingFundRow,
        FinanceTransactionRow,
        MonthlyBudgetRow,
        PersonalFinanceSnapshotRow,
    )
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        for model in (
            FinanceOverviewCacheRow,
            FinanceInsightRow,
            CashflowForecastRow,
            MonthlyBudgetRow,
            FinanceBudgetPlanLineRow,
            FinanceBudgetPlanRow,
            FinanceTransactionRow,
            FinanceImportBatchRow,
            FinanceChangeAuditRow,
            FinanceBackupSnapshotRow,
            FinanceSinkingFundRow,
            FinanceRecurringRuleRow,
            FinanceHealthEventRow,
            FinancePositionSnapshotRow,
            FinanceLiabilityRow,
            FinanceAccountRow,
            PersonalFinanceSnapshotRow,
            BusinessFinanceSnapshotRow,
        ):
            await db.execute(delete(model))
        await db.commit()
    yield


@pytest_asyncio.fixture(autouse=True)
async def reset_integration_settings(setup_db: None) -> AsyncGenerator[None, None]:
    from sqlalchemy import delete

    from app.db.models import AppSettingRow
    from app.db.session import SessionLocal

    async with SessionLocal() as db:
        await db.execute(
            delete(AppSettingRow).where(
                AppSettingRow.key.in_(
                    [
                        "quickfile",
                        "quickfile_last_sync_at",
                        "truelayer",
                        "truelayer_tokens",
                        "truelayer_last_sync_at",
                        "truelayer_monthly_flow",
                        "lunchflow",
                        "lunchflow_last_sync_at",
                        "lunchflow_last_test_at",
                        "lunchflow_monthly_flow",
                        "funding_circle",
                        "funding_circle_last_sync_at",
                        "tesla",
                        "tesla_last_sync_at",
                    ]
                )
            )
        )
        await db.execute(
            delete(AppSettingRow).where(AppSettingRow.key.like("auth.magic.%"))
        )
        await db.commit()
    yield


@pytest_asyncio.fixture(autouse=True)
async def reset_safety_settings(setup_db: None) -> AsyncGenerator[None, None]:
    from sqlalchemy import delete

    from app.db.models import AppSettingRow
    from app.db.session import SessionLocal
    from app.services.safety_settings_service import safety_settings_service

    async with SessionLocal() as db:
        await db.execute(delete(AppSettingRow).where(AppSettingRow.key == "safety_settings"))
        await db.commit()
    safety_settings_service._overrides = None
    yield
    async with SessionLocal() as db:
        await db.execute(delete(AppSettingRow).where(AppSettingRow.key == "safety_settings"))
        await db.commit()
    safety_settings_service._overrides = None


@pytest_asyncio.fixture(autouse=True)
async def reset_write_rate_limiter() -> AsyncGenerator[None, None]:
    from app.middleware.rate_limit import write_rate_limiter

    write_rate_limiter._events.clear()
    yield


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def login(client: AsyncClient, username: str, password: str) -> dict:
    response = await client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    data = response.json()
    return data
