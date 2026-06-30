"""Whole-home savings reconciliation — Octopus meter vs inverter estimates."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import MetricSampleRow
from app.schemas.domain import HistoryRange, ReconciliationInterval, ReconciliationResponse
from app.services.analytics_service import _integrate_kwh, _range_start, analytics_service
from app.services.iog_schedule import charge_intervals_from_windows, is_charge_minute
from app.services.octopus_client import octopus_client


def _parse_interval(raw: dict) -> tuple[datetime, datetime, float] | None:
    start_raw = raw.get("interval_start")
    end_raw = raw.get("interval_end")
    if not start_raw or not end_raw:
        return None
    try:
        start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    try:
        kwh = float(raw.get("consumption") or 0)
    except (TypeError, ValueError):
        kwh = 0.0
    return start, end, kwh


def _interval_is_cheap(
    start: datetime,
    end: datetime,
    charge_intervals: list[tuple[int, int]],
) -> bool:
    """Classify interval as cheap if midpoint falls in IOG off-peak or dispatch (UK)."""
    mid = start + (end - start) / 2
    local = mid.astimezone(ZoneInfo("Europe/London"))
    minute = local.hour * 60 + local.minute
    return is_charge_minute(minute, charge_intervals)


class BillingReconciliationService:
    async def get_reconciliation(
        self,
        db: AsyncSession,
        range_name: HistoryRange,
    ) -> ReconciliationResponse:
        if not octopus_client.configured():
            return ReconciliationResponse(
                range=range_name,
                meter_import_kwh=0,
                cheap_import_kwh=0,
                day_import_kwh=0,
                export_kwh=0,
                import_cost_gbp=0,
                export_earnings_gbp=0,
                net_bill_impact_gbp=0,
                inverter_estimate_gbp=0,
                delta_gbp=0,
                configured=False,
                message="Octopus API not configured",
            )

        range_start = _range_start(range_name)
        try:
            dispatches = await octopus_client.get_dispatches()
        except Exception:
            return ReconciliationResponse(
                range=range_name,
                meter_import_kwh=0,
                cheap_import_kwh=0,
                day_import_kwh=0,
                export_kwh=0,
                import_cost_gbp=0,
                export_earnings_gbp=0,
                net_bill_impact_gbp=0,
                inverter_estimate_gbp=0,
                delta_gbp=0,
                configured=False,
                message="Octopus data unavailable",
            )

        charge_intervals = charge_intervals_from_windows(
            dispatches.off_peak_window.start,
            dispatches.off_peak_window.end,
            list(dispatches.planned) + list(dispatches.completed),
        )

        page_size = {"day": 48, "week": 336, "month": 1440}[range_name.value]
        raw_intervals = await octopus_client.get_consumption(page_size=page_size)

        meter_import = 0.0
        cheap_import = 0.0
        day_import = 0.0
        intervals: list[ReconciliationInterval] = []

        for raw in raw_intervals:
            parsed = _parse_interval(raw)
            if parsed is None:
                continue
            start, end, kwh = parsed
            if end <= range_start:
                continue
            if kwh <= 0:
                continue
            meter_import += kwh
            is_cheap = _interval_is_cheap(start, end, charge_intervals)
            if is_cheap:
                cheap_import += kwh
            else:
                day_import += kwh
            intervals.append(
                ReconciliationInterval(
                    start=start,
                    end=end,
                    consumption_kwh=round(kwh, 4),
                    is_cheap=is_cheap,
                )
            )

        result = await db.execute(
            select(MetricSampleRow)
            .where(MetricSampleRow.timestamp >= range_start)
            .order_by(MetricSampleRow.timestamp.asc())
        )
        rows = list(result.scalars().all())
        export_kwh = _integrate_kwh(rows, "grid_export_w")

        try:
            tariff = await octopus_client.get_tariff_info()
            day_rate = (tariff.import_rate_pence or 28.0) / 100.0
            export_rate = (tariff.export_rate_pence or 15.0) / 100.0
            offpeak_rate = settings.iog_offpeak_rate_gbp
        except Exception:
            day_rate = settings.tariff_import_rate
            export_rate = settings.tariff_export_rate
            offpeak_rate = settings.iog_offpeak_rate_gbp

        import_cost = cheap_import * offpeak_rate + day_import * day_rate
        export_earnings = export_kwh * export_rate
        net_bill = import_cost - export_earnings

        summary = await analytics_service.get_summary(db, range_name)
        inverter_estimate = summary.savings
        delta = net_bill - (-inverter_estimate) if inverter_estimate else net_bill

        return ReconciliationResponse(
            range=range_name,
            meter_import_kwh=round(meter_import, 3),
            cheap_import_kwh=round(cheap_import, 3),
            day_import_kwh=round(day_import, 3),
            export_kwh=round(export_kwh, 3),
            import_cost_gbp=round(import_cost, 2),
            export_earnings_gbp=round(export_earnings, 2),
            net_bill_impact_gbp=round(net_bill, 2),
            inverter_estimate_gbp=round(inverter_estimate, 2),
            delta_gbp=round(delta, 2),
            currency="GBP",
            intervals=intervals[-96:],
            configured=True,
            message="",
        )


billing_reconciliation_service = BillingReconciliationService()
