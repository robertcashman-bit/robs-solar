"""Finance API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_viewer
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.quickfile_provider import QuickFileProvider
from app.integrations.registry import integration_registry
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.finance import (
    BusinessFinanceSnapshot,
    BusinessFinanceSnapshotCreate,
    CashflowForecastEntry,
    CashflowForecastEntryCreate,
    CashflowForecastResponse,
    FinanceAccount,
    FinanceAccountCreate,
    FinanceAccountUpdate,
    FinanceLiability,
    FinanceLiabilityCreate,
    FinanceLiabilityUpdate,
    FinanceOverviewResponse,
    FinanceReportsResponse,
    FinanceScope,
    MonthlyBudgetLine,
    MonthlyBudgetLineCreate,
    MonthlyBudgetLineUpdate,
    PersonalFinanceSnapshot,
    PersonalFinanceSnapshotCreate,
    QuickFileConfig,
    QuickFileConfigStatus,
    QuickFileSyncResult,
)
from app.services.finance.debt_strategy_service import recommend_debt_strategy
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_budget_service import finance_budget_service
from app.services.finance.finance_cashflow_service import finance_cashflow_service
from app.services.finance.finance_insights_service import finance_insights_service
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service
from app.services.finance.finance_reports_service import finance_reports_service
from app.services.finance.quickfile_sync_service import quickfile_sync_service
from app.services.quickfile_settings_service import quickfile_settings_service

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/overview", response_model=FinanceOverviewResponse)
async def get_overview(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> FinanceOverviewResponse:
    return await finance_overview_service.get_overview(db)


@router.get("/accounts", response_model=list[FinanceAccount])
async def list_accounts(
    scope: FinanceScope | None = None,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[FinanceAccount]:
    return await finance_accounts_service.list_accounts(db, scope=scope)


@router.post("/accounts", response_model=FinanceAccount, status_code=status.HTTP_201_CREATED)
async def create_account(
    request: Request,
    body: FinanceAccountCreate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FinanceAccount:
    await enforce_write_rate_limit(request)
    return await finance_accounts_service.create(db, body)


@router.put("/accounts/{account_id}", response_model=FinanceAccount)
async def update_account(
    request: Request,
    account_id: int,
    body: FinanceAccountUpdate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FinanceAccount:
    await enforce_write_rate_limit(request)
    result = await finance_accounts_service.update(db, account_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return result


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    request: Request,
    account_id: int,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await enforce_write_rate_limit(request)
    if not await finance_accounts_service.delete(db, account_id):
        raise HTTPException(status_code=404, detail="Account not found")


@router.get("/liabilities", response_model=list[FinanceLiability])
async def list_liabilities(
    scope: FinanceScope | None = None,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[FinanceLiability]:
    return await finance_liabilities_service.list_liabilities(db, scope=scope)


@router.post("/liabilities", response_model=FinanceLiability, status_code=status.HTTP_201_CREATED)
async def create_liability(
    request: Request,
    body: FinanceLiabilityCreate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FinanceLiability:
    await enforce_write_rate_limit(request)
    return await finance_liabilities_service.create(db, body)


@router.put("/liabilities/{liability_id}", response_model=FinanceLiability)
async def update_liability(
    request: Request,
    liability_id: int,
    body: FinanceLiabilityUpdate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FinanceLiability:
    await enforce_write_rate_limit(request)
    result = await finance_liabilities_service.update(db, liability_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Liability not found")
    return result


@router.delete("/liabilities/{liability_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_liability(
    request: Request,
    liability_id: int,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await enforce_write_rate_limit(request)
    if not await finance_liabilities_service.delete(db, liability_id):
        raise HTTPException(status_code=404, detail="Liability not found")


@router.get("/debts/strategy")
async def get_debt_strategy(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    liabilities = await finance_liabilities_service.list_liabilities(db)
    return recommend_debt_strategy(liabilities)


@router.get("/snapshots/personal", response_model=list[PersonalFinanceSnapshot])
async def list_personal_snapshots(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[PersonalFinanceSnapshot]:
    return await finance_overview_service.list_personal_snapshots(db)


@router.post(
    "/snapshots/personal",
    response_model=PersonalFinanceSnapshot,
    status_code=status.HTTP_201_CREATED,
)
async def create_personal_snapshot(
    request: Request,
    body: PersonalFinanceSnapshotCreate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PersonalFinanceSnapshot:
    await enforce_write_rate_limit(request)
    return await finance_overview_service.create_personal_snapshot(db, body)


@router.get("/snapshots/business", response_model=list[BusinessFinanceSnapshot])
async def list_business_snapshots(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[BusinessFinanceSnapshot]:
    return await finance_overview_service.list_business_snapshots(db)


@router.post(
    "/snapshots/business",
    response_model=BusinessFinanceSnapshot,
    status_code=status.HTTP_201_CREATED,
)
async def create_business_snapshot(
    request: Request,
    body: BusinessFinanceSnapshotCreate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BusinessFinanceSnapshot:
    await enforce_write_rate_limit(request)
    return await finance_overview_service.create_business_snapshot(db, body)


@router.get("/budget", response_model=list[MonthlyBudgetLine])
async def get_budget(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    scope: FinanceScope | None = None,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[MonthlyBudgetLine]:
    return await finance_budget_service.list_budget(db, month=month, scope=scope)


@router.put("/budget", response_model=MonthlyBudgetLine)
async def upsert_budget_line(
    request: Request,
    body: MonthlyBudgetLineCreate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MonthlyBudgetLine:
    await enforce_write_rate_limit(request)
    return await finance_budget_service.upsert_line(db, body)


@router.patch("/budget/{line_id}", response_model=MonthlyBudgetLine)
async def update_budget_line(
    request: Request,
    line_id: int,
    body: MonthlyBudgetLineUpdate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> MonthlyBudgetLine:
    await enforce_write_rate_limit(request)
    result = await finance_budget_service.update_line(db, line_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Budget line not found")
    return result


@router.get("/cashflow", response_model=CashflowForecastResponse)
async def get_cashflow(
    horizon: int = Query(default=30, ge=30, le=90),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> CashflowForecastResponse:
    return await finance_cashflow_service.build_forecast(db, horizon_days=horizon)


@router.post("/cashflow", response_model=CashflowForecastEntry, status_code=status.HTTP_201_CREATED)
async def create_cashflow_entry(
    request: Request,
    body: CashflowForecastEntryCreate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CashflowForecastEntry:
    await enforce_write_rate_limit(request)
    return await finance_cashflow_service.create_entry(db, body)


@router.get("/insights")
async def list_insights(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    return await finance_insights_service.generate_and_list(db)


@router.post("/insights/{insight_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_insight(
    request: Request,
    insight_id: int,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await enforce_write_rate_limit(request)
    if not await finance_insights_service.dismiss(db, insight_id):
        raise HTTPException(status_code=404, detail="Insight not found")


@router.get("/reports", response_model=FinanceReportsResponse)
async def get_reports(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> FinanceReportsResponse:
    return await finance_reports_service.get_reports(db, month=month)


@router.get("/integrations")
async def list_integrations(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, str]]:
    providers = integration_registry.list_providers()
    qf_status = await quickfile_settings_service.get_status(db)
    for provider in providers:
        if provider["id"] == "quickfile":
            provider["status"] = "active" if qf_status.configured else "inactive"
    return providers


@router.get("/integrations/quickfile/status", response_model=QuickFileConfigStatus)
async def quickfile_status(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> QuickFileConfigStatus:
    return await quickfile_settings_service.get_status(db)


@router.put("/integrations/quickfile/settings", response_model=QuickFileConfigStatus)
async def quickfile_save_settings(
    request: Request,
    body: QuickFileConfig,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> QuickFileConfigStatus:
    await enforce_write_rate_limit(request)
    return await quickfile_settings_service.set_config(db, body)


@router.post("/integrations/quickfile/test")
async def quickfile_test_connection(
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await enforce_write_rate_limit(request)
    config = await quickfile_settings_service.get_config(db)
    provider = QuickFileProvider(config)
    try:
        result = await provider.test_connection()
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/integrations/quickfile/sync", response_model=QuickFileSyncResult)
async def quickfile_sync(
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> QuickFileSyncResult:
    await enforce_write_rate_limit(request)
    config = await quickfile_settings_service.get_config(db)
    try:
        return await quickfile_sync_service.sync(db, config)
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
