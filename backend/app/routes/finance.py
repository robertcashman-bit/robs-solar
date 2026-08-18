"""Finance API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.cron import require_cron_secret
from app.auth.dependencies import require_admin, require_viewer, validate_csrf
from app.auth.sessions import SessionData
from app.config import settings
from app.db.session import get_db
from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.quickfile_client import QuickFileError
from app.integrations.quickfile_provider import QuickFileProvider
from app.integrations.registry import integration_registry
from app.integrations.tesla_provider import TeslaProvider
from app.integrations.truelayer_client import TrueLayerClient
from app.integrations.truelayer_provider import TrueLayerProvider
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.finance import (
    BudgetCompareResponse,
    BudgetPlan,
    BudgetPlanCreate,
    BudgetPlanFromHistory,
    BudgetPlanFromSuggestion,
    BudgetPlanUpdate,
    BudgetStarterRequest,
    BudgetSuggestionsResponse,
    BudgetVsActualResponse,
    BusinessFinanceSnapshot,
    BusinessFinanceSnapshotCreate,
    CashflowForecastEntry,
    CashflowForecastEntryCreate,
    CashflowForecastEntryUpdate,
    CashflowForecastResponse,
    DebtScenarioResult,
    FinanceAccount,
    FinanceAccountCreate,
    FinanceAccountUpdate,
    FinanceDailySyncResult,
    FinanceLiability,
    FinanceLiabilityCreate,
    FinanceLiabilityUpdate,
    FinanceOverviewResponse,
    FinanceReportsResponse,
    FinanceScope,
    FundingCircleConfig,
    FundingCircleConfigStatus,
    FundingCircleSyncResult,
    LunchFlowConfig,
    LunchFlowConfigStatus,
    LunchFlowSyncResult,
    MonthlyBudgetBatchWrite,
    MonthlyBudgetLine,
    MonthlyBudgetLineCreate,
    MonthlyBudgetLineUpdate,
    PersonalFinanceSnapshot,
    PersonalFinanceSnapshotCreate,
    QuickFileBudgetAccountsUpdate,
    QuickFileConfig,
    QuickFileConfigStatus,
    QuickFileReportsResponse,
    QuickFileSyncResult,
    TeslaChargingStatus,
    TeslaConfig,
    TeslaConfigStatus,
    TrueLayerConfig,
    TrueLayerConfigStatus,
    TrueLayerSyncResult,
)
from app.services.finance.debt_strategy_service import recommend_debt_strategy, scenario_for_extra
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_budget_plan_service import finance_budget_plan_service
from app.services.finance.finance_budget_service import finance_budget_service
from app.services.finance.finance_cashflow_service import finance_cashflow_service
from app.services.finance.finance_daily_sync_service import finance_daily_sync_service
from app.services.finance.finance_insights_service import finance_insights_service
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service
from app.services.finance.finance_reports_service import finance_reports_service
from app.services.finance.funding_circle_sync_service import funding_circle_sync_service
from app.services.finance.lunchflow_sync_service import lunchflow_sync_service
from app.services.finance.quickfile_reports_service import quickfile_reports_service
from app.services.finance.quickfile_sync_service import quickfile_sync_service
from app.services.finance.truelayer_sync_service import truelayer_sync_service
from app.services.funding_circle_settings_service import funding_circle_settings_service
from app.services.lunchflow_settings_service import lunchflow_settings_service
from app.services.quickfile_settings_service import quickfile_settings_service
from app.services.tesla_settings_service import tesla_settings_service
from app.services.truelayer_settings_service import truelayer_settings_service

router = APIRouter(prefix="/finance", tags=["finance"])


def require_admin_csrf(
    request: Request, session: SessionData = Depends(require_admin)
) -> SessionData:
    validate_csrf(request, session)
    return session


@router.get("/overview", response_model=FinanceOverviewResponse)
async def get_overview(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    live: bool = Query(default=False),
    fresh: bool = Query(default=False),
    period: str | None = Query(default=None, pattern=r"^(mtd|1m|3m|6m|12m)$"),
    personal_period: str | None = Query(default=None, pattern=r"^(mtd|1m|3m|6m|12m)$"),
    business_period: str | None = Query(default=None, pattern=r"^(mtd|1m|3m|6m|12m)$"),
    scope: str | None = Query(default=None, pattern=r"^(personal|business|both)$"),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> FinanceOverviewResponse:
    # `period` is the shared default; personal/business can override independently.
    personal = personal_period or period or "1m"
    business = business_period or period or "1m"
    _ = scope  # accepted for clients; overview always returns both period flows
    return await finance_overview_service.get_overview(
        db,
        month=month,
        refresh_live=live,
        fresh=fresh,
        personal_period=personal,
        business_period=business,
    )


@router.post("/live-refresh")
async def finance_live_refresh(
    request: Request,
    full: bool = Query(default=False),
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_live_refresh_service import (
        finance_live_refresh_service,
    )

    # Default: balances + reports only. Full=True also pulls Lunch Flow txs.
    await finance_live_refresh_service.ensure_fresh(db, include_transactions=full)
    return {
        "ok": True,
        "message": "Live connections refreshed",
        "include_transactions": full,
    }


@router.get("/accounts", response_model=list[FinanceAccount])
async def list_accounts(
    scope: FinanceScope | None = None,
    live: bool = Query(default=False),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[FinanceAccount]:
    return await finance_accounts_service.list_accounts(
        db, scope=scope, refresh_live=live
    )


@router.post("/accounts", response_model=FinanceAccount, status_code=status.HTTP_201_CREATED)
async def create_account(
    request: Request,
    body: FinanceAccountCreate,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> FinanceAccount:
    await enforce_write_rate_limit(request)
    account = await finance_accounts_service.create(db, body)
    await finance_liabilities_service.ensure_from_accounts(db)
    return account


@router.put("/accounts/{account_id}", response_model=FinanceAccount)
async def update_account(
    request: Request,
    account_id: int,
    body: FinanceAccountUpdate,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> FinanceAccount:
    await enforce_write_rate_limit(request)
    result = await finance_accounts_service.update(db, account_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Account not found")
    await finance_liabilities_service.ensure_from_accounts(db)
    return result


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    request: Request,
    account_id: int,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> None:
    await enforce_write_rate_limit(request)
    if not await finance_accounts_service.delete(db, account_id):
        raise HTTPException(status_code=404, detail="Account not found")
    await finance_liabilities_service.archive_for_account(db, account_id)


@router.get("/liabilities", response_model=list[FinanceLiability])
async def list_liabilities(
    scope: FinanceScope | None = None,
    live: bool = Query(default=False),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[FinanceLiability]:
    return await finance_liabilities_service.list_liabilities(
        db, scope=scope, sync_accounts=live
    )


@router.post("/liabilities", response_model=FinanceLiability, status_code=status.HTTP_201_CREATED)
async def create_liability(
    request: Request,
    body: FinanceLiabilityCreate,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> FinanceLiability:
    await enforce_write_rate_limit(request)
    return await finance_liabilities_service.create(db, body)


@router.put("/liabilities/{liability_id}", response_model=FinanceLiability)
async def update_liability(
    request: Request,
    liability_id: int,
    body: FinanceLiabilityUpdate,
    session: SessionData = Depends(require_admin_csrf),
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
    session: SessionData = Depends(require_admin_csrf),
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
    liabilities = await finance_liabilities_service.list_liabilities(
        db, sync_accounts=False
    )
    return recommend_debt_strategy(liabilities)


@router.get("/debts/scenarios", response_model=list[DebtScenarioResult])
async def get_debt_scenarios(
    extra: float = Query(default=0, ge=0),
    extras: str | None = Query(default=None),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[DebtScenarioResult]:
    liabilities = await finance_liabilities_service.list_liabilities(
        db, sync_accounts=False
    )
    amounts = [0.0, 100.0, 250.0, 500.0]
    if extras:
        parsed = []
        for part in extras.split(","):
            try:
                parsed.append(float(part.strip()))
            except ValueError:
                continue
        if parsed:
            amounts = parsed
    if extra and extra not in amounts:
        amounts.append(extra)
    return [scenario_for_extra(liabilities, amount) for amount in amounts]


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
    session: SessionData = Depends(require_admin_csrf),
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
    session: SessionData = Depends(require_admin_csrf),
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


@router.post("/budget/starter", response_model=list[MonthlyBudgetLine])
async def seed_starter_budget(
    request: Request,
    body: BudgetStarterRequest,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[MonthlyBudgetLine]:
    await enforce_write_rate_limit(request)
    plan_amounts: dict[str, float] = {}
    if body.from_active_plan:
        plan = await finance_budget_plan_service.get_active(db)
        if plan is not None:
            plan_amounts = {
                line.category: line.amount_gbp
                for line in plan.lines
                if line.scope == body.scope
            }
    return await finance_budget_service.ensure_starter_lines(
        db,
        month=body.month,
        scope=body.scope,
        plan_amounts=plan_amounts,
    )


@router.put("/budget", response_model=MonthlyBudgetLine)
async def upsert_budget_line(
    request: Request,
    body: MonthlyBudgetLineCreate,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> MonthlyBudgetLine:
    await enforce_write_rate_limit(request)
    return await finance_budget_service.upsert_line(db, body)


@router.put("/budget/batch", response_model=list[MonthlyBudgetLine])
async def upsert_budget_lines(
    request: Request,
    body: MonthlyBudgetBatchWrite,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[MonthlyBudgetLine]:
    await enforce_write_rate_limit(request)
    return await finance_budget_service.upsert_lines(db, body.lines)


@router.patch("/budget/{line_id}", response_model=MonthlyBudgetLine)
async def update_budget_line(
    request: Request,
    line_id: int,
    body: MonthlyBudgetLineUpdate,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> MonthlyBudgetLine:
    await enforce_write_rate_limit(request)
    result = await finance_budget_service.update_line(db, line_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Budget line not found")
    return result


@router.delete("/budget/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget_line(
    request: Request,
    line_id: int,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await enforce_write_rate_limit(request)
    if not await finance_budget_service.delete_line(db, line_id):
        raise HTTPException(status_code=404, detail="Budget line not found")


@router.get("/budgets", response_model=list[BudgetPlan])
async def list_budget_plans(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[BudgetPlan]:
    return await finance_budget_plan_service.list_plans(db)


@router.get("/budgets/suggestions", response_model=BudgetSuggestionsResponse)
async def get_budget_suggestions(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> BudgetSuggestionsResponse:
    return await finance_budget_plan_service.suggestions(db)


@router.get("/budgets/compare", response_model=BudgetCompareResponse)
async def compare_budgets(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> BudgetCompareResponse:
    return await finance_budget_plan_service.compare(db)


@router.get("/budgets/vs-actual", response_model=BudgetVsActualResponse)
async def budget_vs_actual(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    scope: FinanceScope | None = None,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> BudgetVsActualResponse:
    return await finance_budget_plan_service.vs_actual(
        db, month, scope=scope.value if scope else None
    )


@router.get("/budgets/active", response_model=Optional[BudgetPlan])
async def get_active_budget(
    scope: FinanceScope | None = None,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> BudgetPlan | None:
    return await finance_budget_plan_service.get_active(
        db, scope=scope.value if scope else None
    )


@router.get("/budgets/from-history")
async def preview_history_budget_early(
    scope: FinanceScope,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.finance.history_budget_service import history_budget_service

    return await history_budget_service.preview(db, scope.value)


@router.post(
    "/budgets/from-history",
    response_model=BudgetPlan,
    status_code=status.HTTP_201_CREATED,
)
async def create_history_budget_early(
    request: Request,
    body: BudgetPlanFromHistory,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BudgetPlan:
    await enforce_write_rate_limit(request)
    from app.services.finance.history_budget_service import history_budget_service

    return await history_budget_service.create_plan(db, body)


@router.get("/budgets/{plan_id}", response_model=BudgetPlan)
async def get_budget_plan(
    plan_id: int,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> BudgetPlan:
    plan = await finance_budget_plan_service.get(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    return plan


@router.post("/budgets", response_model=BudgetPlan, status_code=status.HTTP_201_CREATED)
async def create_budget_plan(
    request: Request,
    body: BudgetPlanCreate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BudgetPlan:
    await enforce_write_rate_limit(request)
    return await finance_budget_plan_service.create(db, body)


@router.post(
    "/budgets/from-suggestion",
    response_model=BudgetPlan,
    status_code=status.HTTP_201_CREATED,
)
async def create_budget_from_suggestion(
    request: Request,
    body: BudgetPlanFromSuggestion,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BudgetPlan:
    await enforce_write_rate_limit(request)
    try:
        return await finance_budget_plan_service.create_from_suggestion(db, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/budgets/{plan_id}", response_model=BudgetPlan)
async def update_budget_plan(
    request: Request,
    plan_id: int,
    body: BudgetPlanUpdate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BudgetPlan:
    await enforce_write_rate_limit(request)
    result = await finance_budget_plan_service.update(db, plan_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    return result


@router.post(
    "/budgets/{plan_id}/duplicate",
    response_model=BudgetPlan,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_budget_plan(
    request: Request,
    plan_id: int,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BudgetPlan:
    await enforce_write_rate_limit(request)
    result = await finance_budget_plan_service.duplicate(db, plan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    return result


@router.post("/budgets/{plan_id}/activate", response_model=BudgetPlan)
async def activate_budget_plan(
    request: Request,
    plan_id: int,
    scope: FinanceScope | None = None,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BudgetPlan:
    await enforce_write_rate_limit(request)
    result = await finance_budget_plan_service.activate(
        db, plan_id, scope=scope.value if scope else None
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    return result


@router.delete("/budgets/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget_plan(
    request: Request,
    plan_id: int,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await enforce_write_rate_limit(request)
    if not await finance_budget_plan_service.delete(db, plan_id):
        raise HTTPException(status_code=404, detail="Budget not found")


@router.get("/cashflow", response_model=CashflowForecastResponse)
async def get_cashflow(
    horizon: int = Query(default=30, ge=7, le=365),
    scope: FinanceScope | None = None,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> CashflowForecastResponse:
    return await finance_cashflow_service.build_forecast(
        db, horizon_days=horizon, scope=scope
    )


@router.post("/cashflow", response_model=CashflowForecastEntry, status_code=status.HTTP_201_CREATED)
async def create_cashflow_entry(
    request: Request,
    body: CashflowForecastEntryCreate,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> CashflowForecastEntry:
    await enforce_write_rate_limit(request)
    return await finance_cashflow_service.create_entry(db, body)


@router.patch("/cashflow/{entry_id}", response_model=CashflowForecastEntry)
async def update_cashflow_entry(
    request: Request,
    entry_id: int,
    body: CashflowForecastEntryUpdate,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CashflowForecastEntry:
    await enforce_write_rate_limit(request)
    result = await finance_cashflow_service.update_entry(db, entry_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Cashflow entry not found")
    return result


@router.delete("/cashflow/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cashflow_entry(
    request: Request,
    entry_id: int,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await enforce_write_rate_limit(request)
    if not await finance_cashflow_service.delete_entry(db, entry_id):
        raise HTTPException(status_code=404, detail="Cashflow entry not found")


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
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> None:
    await enforce_write_rate_limit(request)
    if not await finance_insights_service.dismiss(db, insight_id):
        raise HTTPException(status_code=404, detail="Insight not found")


@router.get("/reports", response_model=FinanceReportsResponse)
async def get_reports(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    period: str = Query(default="1m", pattern=r"^(mtd|1m|3m|6m|12m)$"),
    scope: str | None = Query(default=None, pattern=r"^(personal|business|both)$"),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> FinanceReportsResponse:
    return await finance_reports_service.get_reports(
        db, month=month, period=period, scope=scope
    )


@router.get("/integrations")
async def list_integrations(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, str]]:
    providers = integration_registry.list_providers()
    qf_status = await quickfile_settings_service.get_status(db)
    ob_status = await truelayer_settings_service.get_status(db)
    lf_status = await lunchflow_settings_service.get_status(db)
    fc_status = await funding_circle_settings_service.get_status(db)
    for provider in providers:
        if provider["id"] == "quickfile":
            provider["status"] = "active" if qf_status.configured else "inactive"
        if provider["id"] == "open_banking":
            if ob_status.connected or lf_status.connected:
                provider["status"] = "active"
            elif ob_status.configured or lf_status.configured:
                provider["status"] = "inactive"
        if provider["id"] == "lunchflow":
            provider["status"] = "active" if lf_status.connected else "inactive"
        if provider["id"] == "funding_circle":
            provider["status"] = (
                "active" if fc_status.configured or ob_status.connected else "inactive"
            )
    hidden = {"octopus", "sunsynk", "tesla"}
    return [provider for provider in providers if provider["id"] not in hidden]


@router.get("/cron/daily-sync", response_model=FinanceDailySyncResult)
async def finance_daily_sync(
    _: None = Depends(require_cron_secret),
) -> FinanceDailySyncResult:
    return await finance_daily_sync_service.sync_once()


@router.get("/cron/daily-backup")
async def finance_daily_backup(
    _: None = Depends(require_cron_secret),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.finance.finance_backup_service import create_backup

    return await create_backup(db, trigger="daily_backup", actor="system")


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
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> QuickFileConfigStatus:
    await enforce_write_rate_limit(request)
    return await quickfile_settings_service.set_config(db, body)


@router.put("/integrations/quickfile/budget-accounts", response_model=QuickFileConfigStatus)
async def quickfile_budget_accounts(
    request: Request,
    body: QuickFileBudgetAccountsUpdate,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> QuickFileConfigStatus:
    """Select which QuickFile bank accounts feed the budget (empty = all)."""
    await enforce_write_rate_limit(request)
    await quickfile_settings_service.set_budget_account_ids(db, body.external_ids)
    return await quickfile_settings_service.get_status(db)


@router.post("/integrations/quickfile/test")
async def quickfile_test_connection(
    request: Request,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await enforce_write_rate_limit(request)
    config = await quickfile_settings_service.get_config(db)
    provider = QuickFileProvider(config)
    try:
        result = await provider.test_connection()
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except QuickFileError as exc:
        await quickfile_settings_service.record_error(db, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await quickfile_settings_service.clear_last_error(db)
    return result


@router.get("/integrations/quickfile/reports", response_model=QuickFileReportsResponse)
async def quickfile_reports(
    live: bool = Query(default=False),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> QuickFileReportsResponse:
    if live:
        reports = await quickfile_reports_service.get_or_refresh_reports(db)
    else:
        reports = await quickfile_reports_service.get_stored_reports(db)
    if reports is None:
        return QuickFileReportsResponse()
    return reports


@router.post("/integrations/quickfile/sync", response_model=QuickFileSyncResult)
async def quickfile_sync(
    request: Request,
    force_full: bool = Query(
        default=False,
        description=(
            "Clear QuickFile full-import markers so this sync uses the ~10-year "
            "lookback window. Existing transactions are not deleted. Daily cron "
            "and live refresh never use this path."
        ),
    ),
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> QuickFileSyncResult:
    await enforce_write_rate_limit(request)
    config = await quickfile_settings_service.get_config(db)
    try:
        return await quickfile_sync_service.sync(db, config, force_full=force_full)
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except QuickFileError as exc:
        await quickfile_settings_service.record_error(db, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/integrations/open-banking/status", response_model=TrueLayerConfigStatus)
async def open_banking_status(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> TrueLayerConfigStatus:
    return await truelayer_settings_service.get_status(db)


@router.put("/integrations/open-banking/settings", response_model=TrueLayerConfigStatus)
async def open_banking_save_settings(
    request: Request,
    body: TrueLayerConfig,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> TrueLayerConfigStatus:
    await enforce_write_rate_limit(request)
    return await truelayer_settings_service.set_config(db, body)


@router.get("/integrations/open-banking/authorize")
async def open_banking_authorize(
    _: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    from app.auth.oidc import create_state

    config = await truelayer_settings_service.get_config(db)
    client = TrueLayerClient(config)
    if not client.configured:
        raise HTTPException(status_code=400, detail="Open Banking is not configured")
    state = create_state()
    return {"authorize_url": client.build_authorize_url(state=state), "state": state}


@router.get("/integrations/open-banking/callback")
async def open_banking_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    from app.auth.oidc import OidcAuthError, verify_state

    origins = settings.cors_origin_list
    frontend = origins[0] if origins else "http://127.0.0.1:3000"
    try:
        verify_state(state)
    except OidcAuthError:
        return RedirectResponse(f"{frontend}/settings?imported=error", status_code=303)
    config = await truelayer_settings_service.get_config(db)
    client = TrueLayerClient(config)
    try:
        tokens = await client.exchange_code(code)
    except Exception:
        return RedirectResponse(f"{frontend}/settings?imported=error", status_code=303)
    await truelayer_settings_service.set_tokens(
        db,
        {
            "access_token": str(tokens.get("access_token", "")),
            "refresh_token": str(tokens.get("refresh_token", "")),
        },
    )
    try:
        await truelayer_sync_service.sync(db, config)
    except Exception:
        return RedirectResponse(f"{frontend}/settings?imported=error", status_code=303)
    return RedirectResponse(f"{frontend}/settings?imported=1", status_code=303)


@router.post("/integrations/open-banking/test")
async def open_banking_test_connection(
    request: Request,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await enforce_write_rate_limit(request)
    config = await truelayer_settings_service.get_config(db)
    tokens = await truelayer_settings_service.get_tokens(db)
    provider = TrueLayerProvider(config, access_token=tokens.get("access_token", ""))
    try:
        return await provider.test_connection()
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/integrations/open-banking/sync", response_model=TrueLayerSyncResult)
async def open_banking_sync(
    request: Request,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> TrueLayerSyncResult:
    await enforce_write_rate_limit(request)
    config = await truelayer_settings_service.get_config(db)
    try:
        return await truelayer_sync_service.sync(db, config)
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/integrations/lunchflow/status", response_model=LunchFlowConfigStatus)
async def lunchflow_status(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> LunchFlowConfigStatus:
    return await lunchflow_settings_service.get_status(db)


@router.put("/integrations/lunchflow/settings", response_model=LunchFlowConfigStatus)
async def lunchflow_save_settings(
    request: Request,
    body: LunchFlowConfig,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> LunchFlowConfigStatus:
    await enforce_write_rate_limit(request)
    return await lunchflow_settings_service.set_config(db, body)


@router.post("/integrations/lunchflow/test")
async def lunchflow_test(
    request: Request,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    config = await lunchflow_settings_service.get_config(db)
    from app.integrations.lunchflow_provider import LunchFlowProvider

    try:
        result = await LunchFlowProvider(config).test_connection()
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await lunchflow_settings_service.mark_tested(db)
    return result


@router.post("/integrations/lunchflow/sync", response_model=LunchFlowSyncResult)
async def lunchflow_sync(
    request: Request,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> LunchFlowSyncResult:
    await enforce_write_rate_limit(request)
    config = await lunchflow_settings_service.get_config(db)
    try:
        return await lunchflow_sync_service.sync(db, config)
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/integrations/funding-circle/status", response_model=FundingCircleConfigStatus)
async def funding_circle_status(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> FundingCircleConfigStatus:
    return await funding_circle_settings_service.get_status(db)


@router.put("/integrations/funding-circle/settings", response_model=FundingCircleConfigStatus)
async def funding_circle_save_settings(
    request: Request,
    body: FundingCircleConfig,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FundingCircleConfigStatus:
    await enforce_write_rate_limit(request)
    return await funding_circle_settings_service.set_config(db, body)


@router.post("/integrations/funding-circle/sync", response_model=FundingCircleSyncResult)
async def funding_circle_sync(
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FundingCircleSyncResult:
    await enforce_write_rate_limit(request)
    return await funding_circle_sync_service.sync(db)


@router.get("/integrations/tesla/status", response_model=TeslaConfigStatus)
async def tesla_status(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> TeslaConfigStatus:
    return await tesla_settings_service.get_status(db)


@router.put("/integrations/tesla/settings", response_model=TeslaConfigStatus)
async def tesla_save_settings(
    request: Request,
    body: TeslaConfig,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> TeslaConfigStatus:
    await enforce_write_rate_limit(request)
    return await tesla_settings_service.set_config(db, body)


@router.get("/integrations/tesla/charging", response_model=TeslaChargingStatus)
async def tesla_charging_status(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> TeslaChargingStatus:
    config = await tesla_settings_service.get_config(db)
    provider = TeslaProvider(config)
    try:
        return await provider.get_charging_status()
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/transactions")
async def list_transactions(
    scope: FinanceScope | None = None,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    category: str | None = None,
    account_id: int | None = None,
    filter_key: str | None = Query(default=None, alias="filter"),
    q: str | None = None,
    min_amount_gbp: float | None = None,
    max_amount_gbp: float | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    source: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from app.services.finance.finance_ledger_service import finance_ledger_service

    return await finance_ledger_service.list_transactions(
        db,
        scope=scope.value if scope else None,
        month=month,
        category=category,
        account_id=account_id,
        filter_key=filter_key,
        q=q,
        min_amount_gbp=min_amount_gbp,
        max_amount_gbp=max_amount_gbp,
        date_from=date_from,
        date_to=date_to,
        source=source,
        limit=limit,
        offset=offset,
    )


@router.post("/transactions/import/parse")
async def parse_statement_import(
    request: Request,
    file: UploadFile = File(...),
    account_name: str = Form(...),
    scope: str = Form("personal"),
    session: SessionData = Depends(require_admin_csrf),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.statement_parsers import parse_statement_bytes

    content = await file.read()
    if len(content) > 8_000_000:
        raise HTTPException(status_code=400, detail="File too large (max 8MB)")
    if not account_name.strip():
        raise HTTPException(status_code=400, detail="Account name is required")
    if scope not in {"personal", "business"}:
        raise HTTPException(status_code=400, detail="Scope must be personal or business")
    return parse_statement_bytes(
        content,
        file.filename or "statement.csv",
        account_name=account_name.strip(),
        scope=scope,
    )


@router.post("/transactions/import/preview")
async def preview_transaction_import(
    request: Request,
    body: dict,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_import_service import finance_import_service

    rows = body.get("rows") if isinstance(body.get("rows"), list) else []
    source = str(body.get("source") or "csv")
    preview = await finance_import_service.preview(db, rows, source=source)
    preview.pop("accepted", None)
    return preview


@router.post("/transactions/import/commit")
async def commit_transaction_import(
    request: Request,
    body: dict,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_backup_service import create_backup
    from app.services.finance.finance_import_service import finance_import_service

    rows = body.get("rows") if isinstance(body.get("rows"), list) else []
    source = str(body.get("source") or "csv")
    result = await finance_import_service.commit(db, rows, source=source, actor="user")
    try:
        await create_backup(db, trigger="manual_import", actor="user")
    except Exception:
        pass
    return result


@router.post("/transactions/bulk-category")
async def bulk_categorise_transactions(
    request: Request,
    body: dict,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_ledger_service import finance_ledger_service

    ids = body.get("ids") if isinstance(body.get("ids"), list) else []
    txn_ids = [int(item) for item in ids if str(item).isdigit() or isinstance(item, int)]
    category = str(body.get("category") or "").strip()
    if not category:
        raise HTTPException(status_code=400, detail="Category is required")
    try:
        return await finance_ledger_service.bulk_categorise(
            db,
            txn_ids,
            category=category,
            create_rule=bool(body.get("create_rule")),
            actor="user",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/transactions/{txn_id}/category")
async def categorise_transaction(
    request: Request,
    txn_id: int,
    body: dict,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_ledger_service import finance_ledger_service

    category = str(body.get("category") or "").strip()
    if not category:
        raise HTTPException(status_code=400, detail="Category is required")
    try:
        result = await finance_ledger_service.set_category(
            db,
            txn_id,
            category=category,
            subcategory=str(body.get("subcategory") or ""),
            create_rule=bool(body.get("create_rule")),
            actor="user",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


@router.delete("/transactions/{txn_id}")
async def delete_transaction(
    request: Request,
    txn_id: int,
    confirm: bool = False,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> None:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_ledger_service import finance_ledger_service

    try:
        deleted = await finance_ledger_service.soft_delete(
            db, txn_id, actor="user", confirm=confirm
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Transaction not found")


@router.post("/transfers/detect")
async def detect_transfers(
    request: Request,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_transfer_service import finance_transfer_service

    return await finance_transfer_service.detect_and_mark(db)


@router.get("/period-flow")
async def period_flow(
    period: str = Query(default="1m", pattern=r"^(mtd|1m|3m|6m|12m)$"),
    scope: FinanceScope = FinanceScope.PERSONAL,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.finance.finance_ledger_service import finance_ledger_service

    return await finance_ledger_service.period_flow_totals(
        db, period=period, scope=scope.value
    )


@router.get("/pnl-compare")
async def pnl_compare(
    scope: FinanceScope = FinanceScope.PERSONAL,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.finance.finance_pnl_compare_service import finance_pnl_compare_service

    return await finance_pnl_compare_service.compare(db, scope=scope.value)


@router.get("/history-stats")
async def history_stats(
    scope: FinanceScope = FinanceScope.PERSONAL,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from app.services.finance.finance_history_stats import finance_history_stats_service

    return await finance_history_stats_service.category_stats(db, scope=scope.value)


@router.get("/history-stats/explain")
async def history_stats_explain(
    category: str,
    scope: FinanceScope = FinanceScope.PERSONAL,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.finance.finance_history_stats import finance_history_stats_service

    return await finance_history_stats_service.explain_category(
        db, scope=scope.value, category=category
    )



@router.post("/finance-ai/interpret")
async def finance_ai_interpret(
    request: Request,
    body: dict,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Interpret overview metrics only — never raw ledger rows."""
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_ai_insights_service import finance_ai_insights_service
    from app.services.finance.finance_overview_service import finance_overview_service

    overview = await finance_overview_service.get_overview(db, refresh_live=False)
    metrics = {
        "cash_status": overview.cash_status,
        "safe_to_spend": overview.safe_to_spend,
        "monthly_income_gbp": overview.monthly_income_gbp,
        "monthly_spending_gbp": overview.monthly_spending_gbp,
        "monthly_surplus_gbp": overview.monthly_surplus_gbp,
        "vat_reserve_gbp": overview.vat_reserve_gbp,
        "corp_tax_reserve_gbp": overview.corp_tax_reserve_gbp,
        "external_debt_gbp": overview.external_debt_gbp,
    }
    prompt = str(body.get("prompt") or "Explain my cashflow")
    return await finance_ai_insights_service.interpret_metrics(metrics, prompt)


@router.get("/data-quality")
async def data_quality_report(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.finance.finance_data_quality_service import finance_data_quality_service

    return await finance_data_quality_service.report(db)


@router.get("/upcoming")
async def upcoming_money(
    days: int = Query(default=30, ge=1, le=365),
    scope: FinanceScope | None = None,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Predicted bills/income from confirmed recurring + cashflow entries."""
    import json
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.db.models import CashflowForecastRow, FinanceRecurringRuleRow
    from app.services.finance.money import quantize_gbp

    today = datetime.now(timezone.utc).date()
    end = today + timedelta(days=days)
    items: list[dict] = []

    stmt = select(FinanceRecurringRuleRow).where(FinanceRecurringRuleRow.status == "confirmed")
    if scope:
        stmt = stmt.where(FinanceRecurringRuleRow.scope == scope.value)
    for row in (await db.scalars(stmt)).all():
        evidence = {}
        try:
            evidence = json.loads(row.evidence_json or "{}")
        except Exception:
            evidence = {}
        next_date = str(evidence.get("expected_next_date") or "")
        if not next_date:
            day = int(evidence.get("typical_day") or today.day)
            day = min(max(day, 1), 28)
            candidate = today.replace(day=day)
            if candidate < today:
                month = today.month + 1
                year = today.year + (1 if month > 12 else 0)
                month = 1 if month > 12 else month
                candidate = candidate.replace(year=year, month=month)
            next_date = candidate.isoformat()
        if today.isoformat() <= next_date <= end.isoformat():
            items.append(
                {
                    "date": next_date,
                    "label": row.description,
                    "amount_gbp": float(quantize_gbp(row.amount_gbp) or 0),
                    "account": row.scope,
                    "confidence": "HIGH",
                    "source": "recurring",
                    "category": row.category,
                }
            )

    cf_stmt = select(CashflowForecastRow).where(
        CashflowForecastRow.forecast_date >= today.isoformat(),
        CashflowForecastRow.forecast_date <= end.isoformat(),
    )
    if scope:
        cf_stmt = cf_stmt.where(CashflowForecastRow.scope == scope.value)
    for row in (await db.scalars(cf_stmt)).all():
        items.append(
            {
                "date": row.forecast_date,
                "label": row.label,
                "amount_gbp": float(row.amount_gbp),
                "account": row.scope,
                "confidence": "HIGH" if row.is_confirmed else "MEDIUM",
                "source": row.source or "cashflow",
                "category": row.entry_type,
            }
        )

    items.sort(key=lambda item: item["date"])
    return {"days": days, "items": items, "count": len(items)}


@router.get("/export/transactions.csv")
async def export_transactions_csv(
    scope: FinanceScope | None = None,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
):
    import csv
    import io

    from app.services.finance.finance_ledger_service import finance_ledger_service

    rows = await finance_ledger_service.list_transactions(
        db, scope=scope.value if scope else None, limit=5000
    )
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "posted_on",
            "scope",
            "account_name",
            "description",
            "amount_gbp",
            "category",
            "txn_type",
            "is_transfer",
            "source",
        ],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key) for key in writer.fieldnames})
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


@router.get("/import-history")
async def import_history(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from sqlalchemy import select

    from app.db.models import FinanceImportBatchRow

    rows = (
        await db.scalars(
            select(FinanceImportBatchRow).order_by(FinanceImportBatchRow.created_at.desc()).limit(40)
        )
    ).all()
    return [
        {
            "id": row.id,
            "source": row.source,
            "status": row.status,
            "detected": row.detected,
            "imported": row.imported,
            "duplicates": row.duplicates,
            "rejected": row.rejected,
            "date_from": row.date_from,
            "date_to": row.date_to,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/audit")
async def finance_audit(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from app.services.finance.finance_audit_service import finance_audit_service

    rows = await finance_audit_service.list_recent(db)
    return [
        {
            "id": row.id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "field": row.field,
            "previous_value": row.previous_value,
            "new_value": row.new_value,
            "actor": row.actor,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/backups")
async def list_finance_backups(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.finance.finance_backup_service import list_backups

    return await list_backups(db)


@router.post("/backups")
async def create_finance_backup(
    request: Request,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_backup_service import create_backup

    return await create_backup(db, trigger="manual", actor="user")


@router.post("/backups/{snapshot_id}/restore")
async def restore_finance_backup(
    request: Request,
    snapshot_id: int,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_backup_service import restore_local_snapshot

    try:
        return await restore_local_snapshot(db, snapshot_id, actor="user")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/categories")
async def list_finance_categories(
    scope: FinanceScope | None = None,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from app.services.finance.category_registry import list_categories

    return await list_categories(db, scope=scope.value if scope else None)


@router.get("/category-rules")
async def list_category_rules(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from app.services.finance.category_registry import list_confirmed_rules

    return await list_confirmed_rules(db)


@router.post("/categories")
async def add_finance_category(
    request: Request,
    body: dict,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    await enforce_write_rate_limit(request)
    from app.services.finance.category_registry import add_custom_category

    scope = str(body.get("scope") or "personal").strip().lower()
    category = str(body.get("category") or "").strip()
    if scope not in {"personal", "business"}:
        raise HTTPException(status_code=400, detail="Scope must be personal or business")
    if not category:
        raise HTTPException(status_code=400, detail="Category is required")
    return await add_custom_category(
        db,
        scope=scope,
        category=category,
        subcategory=str(body.get("subcategory") or ""),
    )


@router.post("/category-rules")
async def confirm_category_rule(
    request: Request,
    body: dict,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.category_registry import confirm_rule

    return await confirm_rule(
        db,
        pattern=str(body.get("pattern") or ""),
        category=str(body.get("category") or ""),
        scope=str(body.get("scope") or "personal"),
    )


@router.get("/recurring")
async def list_recurring(
    scope: FinanceScope | None = None,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from app.services.finance.finance_recurring_service import finance_recurring_service

    return await finance_recurring_service.list_rules(db, scope=scope.value if scope else None)


@router.post("/recurring/detect")
async def detect_recurring(
    request: Request,
    scope: FinanceScope | None = None,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_recurring_service import finance_recurring_service

    return await finance_recurring_service.detect(db, scope=scope.value if scope else None)


@router.post("/recurring/{rule_id}/{action}")
async def set_recurring_status(
    request: Request,
    rule_id: int,
    action: str,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_recurring_service import finance_recurring_service

    if action == "confirm":
        status_value = "confirmed"
    elif action == "reject":
        status_value = "rejected"
    else:
        status_value = action
    try:
        result = await finance_recurring_service.set_status(db, rule_id, status_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Recurring rule not found")
    return result


@router.get("/sinking-funds")
async def list_sinking_funds(
    scope: FinanceScope | None = None,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from app.services.finance.finance_sinking_fund_service import finance_sinking_fund_service

    return await finance_sinking_fund_service.list_funds(db, scope=scope.value if scope else None)


@router.post("/sinking-funds")
async def create_sinking_fund(
    request: Request,
    body: dict,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_sinking_fund_service import finance_sinking_fund_service

    return await finance_sinking_fund_service.create(db, body, actor="user")


@router.put("/sinking-funds/{fund_id}")
async def update_sinking_fund(
    request: Request,
    fund_id: int,
    body: dict,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_sinking_fund_service import finance_sinking_fund_service

    result = await finance_sinking_fund_service.update(db, fund_id, body, actor="user")
    if result is None:
        raise HTTPException(status_code=404, detail="Sinking fund not found")
    return result


@router.delete("/sinking-funds/{fund_id}")
async def delete_sinking_fund(
    request: Request,
    fund_id: int,
    confirm: bool = False,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> None:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_sinking_fund_service import finance_sinking_fund_service

    try:
        deleted = await finance_sinking_fund_service.delete(
            db, fund_id, confirm=confirm, actor="user"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Sinking fund not found")


@router.get("/forecast")
async def month_end_forecast(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    scope: FinanceScope = FinanceScope.PERSONAL,
    category: str = Query(...),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.finance.finance_forecast_service import finance_forecast_service
    from app.services.finance.history_budget_service import history_budget_service

    preview = await history_budget_service.preview(db, scope.value)
    match = next((item for item in preview["lines"] if item["category"] == category), None)
    vs = await finance_budget_plan_service.vs_actual(db, month, scope=scope.value)
    vs_line = next((item for item in vs.lines if item.category == category), None)
    return await finance_forecast_service.month_end(
        db,
        month=month,
        scope=scope.value,
        category=category,
        budget_gbp=vs_line.budget_gbp if vs_line else None,
        actual_gbp=vs_line.actual_gbp if vs_line else None,
        history_run_rate_gbp=(
            match["amount_gbp"] if match and not match["insufficient_data"] else None
        ),
        history_confidence=match["confidence"] if match else "Insufficient data",
    )


@router.get("/reconciliation")
async def finance_reconciliation(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.finance.finance_reconciliation_service import (
        finance_reconciliation_service,
    )

    return await finance_reconciliation_service.report(db)


@router.get("/health")
async def finance_health(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.finance.finance_health_service import finance_health_service

    return await finance_health_service.probe(db)


@router.post("/health/self-heal")
async def finance_self_heal(
    request: Request,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_write_rate_limit(request)
    from app.services.finance.finance_health_service import finance_health_service

    return await finance_health_service.self_heal(db, actor="self_heal")


@router.post("/integrations/tesla/test")
async def tesla_test_connection(
    request: Request,
    session: SessionData = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await enforce_write_rate_limit(request)
    config = await tesla_settings_service.get_config(db)
    provider = TeslaProvider(config)
    try:
        result = await provider.test_connection()
        await tesla_settings_service.mark_synced(db)
        return result
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
