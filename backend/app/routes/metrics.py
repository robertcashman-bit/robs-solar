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
from app.services.analytics_service import analytics_service, enrich_day_summary_with_live
from app.services.battery_plan_service import battery_plan_service
from app.services.billing_reconciliation_service import billing_reconciliation_service
from app.services.charge_window_service import charge_window_service
from app.services.effective_load import finalize_live_metrics
from app.services.ev_load_detector import ev_load_detector, sync_ev_detector
from app.services.live_metrics_cache import live_metrics_cache
from app.services.octopus_client import octopus_client
from app.services.peak_import_guard_service import peak_import_guard_service
from app.services.sell_advisor_service import sell_advisor_service

router = APIRouter(prefix="/metrics", tags=["metrics"])


async def _enrich_with_smart_meter(metrics: LiveMetrics) -> LiveMetrics:
    """Attach Octopus half-hour average when available (cached, non-blocking)."""
    try:
        estimate = await octopus_client.get_meter_power_estimate()
    except Exception:
        return metrics
    if not estimate.configured or estimate.average_power_w is None:
        return metrics
    return metrics.model_copy(
        update={
            "smart_meter_average_w": estimate.average_power_w,
            "smart_meter_interval_start": estimate.interval_start,
            "smart_meter_interval_end": estimate.interval_end,
        }
    )


@router.get("/live", response_model=LiveMetrics)
async def live_metrics(_: SessionData = Depends(require_viewer)) -> LiveMetrics:
    adapter = get_adapter()
    try:
        metrics = await live_metrics_cache.get(adapter)
    except AdapterError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    await sync_ev_detector(metrics)
    finalized = finalize_live_metrics(metrics)
    return await _enrich_with_smart_meter(finalized)


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
    summary = await analytics_service.get_summary(db, range)
    if range != HistoryRange.DAY:
        return summary
    adapter = get_adapter()
    live = live_metrics_cache.peek()
    if live is None:
        try:
            live = await live_metrics_cache.get(adapter)
        except AdapterError:
            return summary
    return await enrich_day_summary_with_live(db, summary, live)


@router.get("/compare", response_model=MetricCompareResponse)
async def metrics_compare(
    range: HistoryRange = HistoryRange.DAY,
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> MetricCompareResponse:
    compare = await analytics_service.get_compare(db, range_name=range)
    if range != HistoryRange.DAY:
        return compare
    adapter = get_adapter()
    live = live_metrics_cache.peek()
    if live is None:
        try:
            live = await live_metrics_cache.get(adapter)
        except AdapterError:
            return compare
    today = await enrich_day_summary_with_live(db, compare.today, live)
    return compare.model_copy(update={"today": today})


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
