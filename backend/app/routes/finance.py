"""Finance API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.cron import require_cron_secret
from app.auth.dependencies import require_admin, require_viewer
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.open_banking_provider import OpenBankingProvider
from app.integrations.quickfile_provider import QuickFileProvider
from app.integrations.registry import integration_registry
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.finance import (
    BankConnectionsResponse,
    BusinessFinanceSnapshot,
    BusinessFinanceSnapshotCreate,
    CashflowForecastEntry,
    CashflowForecastEntryCreate,
    CashflowForecastsResponse,
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
    FinanceTransaction,
    HistoricFinanceSeedResponse,
    MonthlyBudgetLine,
    MonthlyBudgetLineCreate,
    MonthlyBudgetLineUpdate,
    OpenBankingConfig,
    OpenBankingConfigStatus,
    OpenBankingConnectRequest,
    OpenBankingConnectResponse,
    OpenBankingFinalizeRequest,
    OpenBankingInstitution,
    OpenBankingSetupSaveRequest,
    OpenBankingSyncResult,
    OpenBankingTestResult,
    PersonalFinanceSnapshot,
    PersonalFinanceSnapshotCreate,
    QuickFileConfig,
    QuickFileConfigStatus,
    QuickFileReportsResponse,
    QuickFileSyncResult,
)
from app.services.finance.bank_connections_service import (
    TARGET_BANKS,
    get_connections,
    list_transactions,
)
from app.services.finance.bank_connections_service import (
    disconnect as disconnect_bank_connection,
)
from app.services.finance.debt_strategy_service import recommend_debt_strategy
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_budget_service import finance_budget_service
from app.services.finance.finance_cashflow_service import finance_cashflow_service
from app.services.finance.finance_daily_sync_service import sync_once as finance_sync_once
from app.services.finance.finance_insights_service import finance_insights_service
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service
from app.services.finance.finance_reports_service import finance_reports_service
from app.services.finance.historic_finance_seed import seed_historic_finance
from app.services.finance.open_banking_sync_service import open_banking_sync_service
from app.services.finance.quickfile_reports_service import quickfile_reports_service
from app.services.finance.quickfile_sync_service import quickfile_sync_service
from app.services.open_banking_settings_service import open_banking_settings_service
from app.services.open_banking_setup_validation import (
    classify_test_error,
    map_setup_request_to_config,
    run_test_validation,
    success_test_result,
    validate_config,
)
from app.services.quickfile_settings_service import quickfile_settings_service

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/cron/daily-sync", response_model=FinanceDailySyncResult)
async def finance_cron_daily_sync(
    _: None = Depends(require_cron_secret),
) -> FinanceDailySyncResult:
    """Vercel Cron entry point — refreshes Open Banking and QuickFile once per day."""
    return await finance_sync_once()


@router.get("/bank-connections", response_model=BankConnectionsResponse)
async def bank_connections(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> BankConnectionsResponse:
    connections = await get_connections(db)
    return BankConnectionsResponse(connections=connections)


@router.post("/bank-connections/{connection_id}/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def bank_connection_disconnect(
    request: Request,
    connection_id: str,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await enforce_write_rate_limit(request)
    if connection_id not in TARGET_BANKS:
        raise HTTPException(status_code=404, detail="Bank connection not found")
    if not await disconnect_bank_connection(db, connection_id):
        raise HTTPException(
            status_code=400,
            detail="Only Open Banking connections can be disconnected",
        )


@router.post("/bank-connections/{connection_id}/sync", response_model=OpenBankingSyncResult)
async def bank_connection_sync(
    request: Request,
    connection_id: str,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OpenBankingSyncResult:
    await enforce_write_rate_limit(request)
    bank = TARGET_BANKS.get(connection_id)
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank connection not found")

    if bank.method.value == "open_banking":
        config = await open_banking_settings_service.get_config(db)
        try:
            return await open_banking_sync_service.sync(db, config)
        except IntegrationNotConfiguredError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if bank.method.value == "quickfile":
        config = await quickfile_settings_service.get_config(db)
        try:
            result = await quickfile_sync_service.sync(db, config)
            return OpenBankingSyncResult(
                accounts_synced=result.accounts_synced,
                message=result.message,
            )
        except IntegrationNotConfiguredError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return OpenBankingSyncResult(
        accounts_synced=0,
        message="Funding Circle is a manual loan — update the balance on the Connect banks page.",
    )


@router.get("/transactions", response_model=list[FinanceTransaction])
async def finance_transactions(
    limit: int = Query(default=50, ge=1, le=500),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[FinanceTransaction]:
    return await list_transactions(db, limit=limit)


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


@router.get("/cashflow", response_model=CashflowForecastsResponse)
async def get_cashflow(
    horizon: int = Query(default=30, ge=30, le=90),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> CashflowForecastsResponse:
    return await finance_cashflow_service.build_forecasts(db, horizon_days=horizon)


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
    ob_status = await open_banking_settings_service.get_status(db)
    for provider in providers:
        if provider["id"] == "quickfile":
            provider["status"] = "active" if qf_status.configured else "inactive"
        if provider["id"] == "open_banking":
            provider["status"] = "active" if ob_status.configured else "inactive"
    return providers


@router.get("/integrations/quickfile/reports", response_model=QuickFileReportsResponse)
async def quickfile_reports(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> QuickFileReportsResponse:
    reports = await quickfile_reports_service.get_stored_reports(db)
    if reports is None:
        return QuickFileReportsResponse()
    return reports


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


@router.post("/seed/historic", response_model=HistoricFinanceSeedResponse)
async def seed_historic_finance_data(
    request: Request,
    force: bool = Query(default=False),
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> HistoricFinanceSeedResponse:
    await enforce_write_rate_limit(request)
    result = await seed_historic_finance(db, force=force)
    return HistoricFinanceSeedResponse(
        accounts_created=result.accounts_created,
        liabilities_created=result.liabilities_created,
        snapshot_created=result.snapshot_created,
        skipped=result.skipped,
        message=result.message,
    )


@router.get("/integrations/open-banking/status", response_model=OpenBankingConfigStatus)
async def open_banking_status(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> OpenBankingConfigStatus:
    return await open_banking_settings_service.get_status(db)


@router.put("/integrations/open-banking/settings", response_model=OpenBankingConfigStatus)
async def open_banking_save_settings(
    request: Request,
    body: OpenBankingConfig,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OpenBankingConfigStatus:
    await enforce_write_rate_limit(request)
    return await open_banking_settings_service.set_config(db, body)


@router.put("/integrations/open-banking/settings/setup", response_model=OpenBankingConfigStatus)
async def open_banking_save_setup(
    request: Request,
    body: OpenBankingSetupSaveRequest,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OpenBankingConfigStatus:
    """Save Open Banking settings from the plain-English setup form."""
    await enforce_write_rate_limit(request)
    existing = await open_banking_settings_service.get_config(db)
    config = map_setup_request_to_config(body, existing)
    errors = validate_config(config, existing=existing)
    if errors:
        raise HTTPException(status_code=400, detail=errors[0])
    return await open_banking_settings_service.set_config(db, config)


@router.post("/integrations/open-banking/test", response_model=OpenBankingTestResult)
async def open_banking_test_connection(
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OpenBankingTestResult:
    await enforce_write_rate_limit(request)
    existing = await open_banking_settings_service.get_config(db)
    config = existing
    preflight = run_test_validation(config, existing)
    if preflight is not None:
        return preflight

    provider = OpenBankingProvider(config)
    result: dict[str, object] = {}
    try:
        result = await provider.test_connection()
    except IntegrationNotConfiguredError as exc:
        return classify_test_error(exc)
    except Exception as exc:
        return classify_test_error(exc)
    finally:
        from app.services.finance.open_banking_sync_service import _maybe_save_legacy_tokens

        await _maybe_save_legacy_tokens(db, provider)

    return success_test_result(result)


@router.get("/integrations/open-banking/institutions", response_model=list[OpenBankingInstitution])
async def open_banking_institutions(
    country: str = Query(default="gb", min_length=2, max_length=2),
    q: str = Query(default=""),
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[OpenBankingInstitution]:
    config = await open_banking_settings_service.get_config(db)
    provider = OpenBankingProvider(config)
    try:
        rows = await provider.list_institutions(country=country, query=q)
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [OpenBankingInstitution.model_validate(row) for row in rows]


@router.post("/integrations/open-banking/connect", response_model=OpenBankingConnectResponse)
async def open_banking_connect(
    request: Request,
    body: OpenBankingConnectRequest,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OpenBankingConnectResponse:
    await enforce_write_rate_limit(request)
    config = await open_banking_settings_service.get_config(db)
    provider = OpenBankingProvider(config)
    reference = open_banking_settings_service.new_reference()
    redirect_url = open_banking_settings_service.build_redirect_url(config, reference)
    try:
        created = await provider.create_connection(
            institution_id=body.institution_id,
            institution_name=body.institution_name,
            redirect_url=redirect_url,
            reference=reference,
        )
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        from app.services.finance.open_banking_sync_service import _maybe_save_legacy_tokens

        await _maybe_save_legacy_tokens(db, provider)

    from datetime import datetime, timezone

    from app.schemas.finance import OpenBankingRequisition

    requisition = OpenBankingRequisition(
        id=created["requisition_id"],
        institution_id=created["institution_id"],
        institution_name=created["institution_name"],
        status="CR",
        reference=reference,
        state=created.get("state") or reference,
        provider=config.provider,
        created_at=datetime.now(timezone.utc),
    )
    await open_banking_settings_service.upsert_requisition(db, requisition)
    await open_banking_settings_service.store_pending_reference(
        db,
        reference=reference,
        requisition_id=created["requisition_id"],
        institution_id=created["institution_id"],
        institution_name=created["institution_name"],
        provider=config.provider,
    )
    return OpenBankingConnectResponse(
        link=created["link"],
        requisition_id=created["requisition_id"],
        institution_id=created["institution_id"],
        institution_name=created["institution_name"],
        reference=reference,
        state=created.get("state") or reference,
    )


@router.post("/integrations/open-banking/finalize", response_model=OpenBankingSyncResult)
async def open_banking_finalize(
    request: Request,
    body: OpenBankingFinalizeRequest,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OpenBankingSyncResult:
    await enforce_write_rate_limit(request)
    lookup = body.state or body.reference
    if not lookup:
        raise HTTPException(
            status_code=400,
            detail="Missing bank callback reference (state or ref query parameter)",
        )
    pending = await open_banking_settings_service.pop_pending_reference(db, lookup)
    if pending is None:
        raise HTTPException(status_code=404, detail="Bank connection reference not found")

    from app.schemas.finance import OpenBankingRequisition

    config = await open_banking_settings_service.get_config(db)
    provider = OpenBankingProvider(config)
    requisition = OpenBankingRequisition(
        id=pending["requisition_id"],
        institution_id=pending["institution_id"],
        institution_name=pending["institution_name"],
        reference=lookup,
        state=body.state or lookup,
        provider=pending.get("provider") or config.provider,  # type: ignore[arg-type]
    )
    try:
        requisition = await provider.finalize_requisition(requisition, code=body.code)
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        from app.services.finance.open_banking_sync_service import _maybe_save_legacy_tokens

        await _maybe_save_legacy_tokens(db, provider)

    await open_banking_settings_service.upsert_requisition(db, requisition)
    if not provider.is_linked(requisition):
        return OpenBankingSyncResult(
            accounts_synced=0,
            message=(
                f"Bank authorisation status is {requisition.status}. "
                "Complete the bank login, then sync again."
            ),
        )
    try:
        return await open_banking_sync_service.sync(db, config)
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/integrations/open-banking/sync", response_model=OpenBankingSyncResult)
async def open_banking_sync(
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> OpenBankingSyncResult:
    await enforce_write_rate_limit(request)
    config = await open_banking_settings_service.get_config(db)
    provider = OpenBankingProvider(config)
    requisitions = await open_banking_settings_service.list_requisitions(db)
    refreshed: list = []
    for item in requisitions:
        if item.provider == "gocardless":
            try:
                refreshed.append(await provider.finalize_requisition(item))
            except IntegrationNotConfiguredError:
                refreshed.append(item)
        else:
            refreshed.append(item)
    if refreshed:
        await open_banking_settings_service.save_requisitions(db, refreshed)
    try:
        return await open_banking_sync_service.sync(db, config)
    except IntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
