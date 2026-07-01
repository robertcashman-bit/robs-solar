from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_adapter
from app.auth.dependencies import require_admin, require_viewer
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.schemas.domain import (
    AdapterError,
    BatteryPlanStatus,
    ChargeWindowStatus,
    ConnectivityStatus,
    EvStatusResponse,
    HistoryRange,
    LiveMetrics,
    MetricCompareResponse,
    MetricHistoryResponse,
    MetricSummaryResponse,
    PeakImportGuardStatus,
    ReconciliationResponse,
    SellOpportunity,
)
from app.services.analytics_service import analytics_service
from app.services.battery_plan_service import battery_plan_service
from app.services.billing_reconciliation_service import billing_reconciliation_service
from app.services.charge_window_service import charge_window_service
from app.services.ev_load_detector import ev_load_detector, sync_ev_detector
from app.services.peak_import_guard_service import peak_import_guard_service
from app.services.sell_advisor_service import sell_advisor_service

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/live", response_model=LiveMetrics)
async def live_metrics(_: SessionData = Depends(require_viewer)) -> LiveMetrics:
    adapter = get_adapter()
    try:
        metrics = await adapter.get_live_metrics()
    except AdapterError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    await sync_ev_detector(metrics)
    return metrics


@router.get("/connectivity", response_model=ConnectivityStatus)
async def connectivity(_: SessionData = Depends(require_viewer)) -> ConnectivityStatus:
    adapter = get_adapter()
    return await adapter.get_connectivity()


@router.get("/history", response_model=MetricHistoryResponse)
async def metrics_history(
    range: HistoryRange = HistoryRange.DAY,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> MetricHistoryResponse:
    return await analytics_service.get_history(db, range)


@router.get("/summary", response_model=MetricSummaryResponse)
async def metrics_summary(
    range: HistoryRange = HistoryRange.DAY,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> MetricSummaryResponse:
    return await analytics_service.get_summary(db, range)


@router.get("/compare", response_model=MetricCompareResponse)
async def metrics_compare(
    range: HistoryRange = HistoryRange.DAY,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> MetricCompareResponse:
    return await analytics_service.get_compare(db, range_name=range)


@router.get("/reconciliation", response_model=ReconciliationResponse)
async def metrics_reconciliation(
    range: HistoryRange = HistoryRange.DAY,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> ReconciliationResponse:
    return await billing_reconciliation_service.get_reconciliation(db, range)


@router.get("/charge-window", response_model=ChargeWindowStatus)
async def charge_window_status(_: SessionData = Depends(require_viewer)) -> ChargeWindowStatus:
    adapter = get_adapter()
    return await charge_window_service.get_status(adapter)


@router.get("/peak-import-guard", response_model=PeakImportGuardStatus)
async def peak_import_guard_status(
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PeakImportGuardStatus:
    _ = session
    return await peak_import_guard_service.get_status(db)


@router.get("/battery-plan", response_model=BatteryPlanStatus)
async def battery_plan(
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BatteryPlanStatus:
    _ = session
    adapter = get_adapter()
    return await battery_plan_service.get_plan(db, adapter)


@router.get("/sell-opportunity", response_model=SellOpportunity)
async def sell_opportunity(_: SessionData = Depends(require_viewer)) -> SellOpportunity:
    adapter = get_adapter()
    return await sell_advisor_service.get_opportunity(adapter)


@router.get("/ev/status", response_model=EvStatusResponse)
async def ev_status(_: SessionData = Depends(require_viewer)) -> EvStatusResponse:
    adapter = get_adapter()
    try:
        metrics = await adapter.get_live_metrics()
    except AdapterError:
        return ev_load_detector.status()
    await sync_ev_detector(metrics)
    return ev_load_detector.status(metrics)
