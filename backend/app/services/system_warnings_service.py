"""System warnings catalogue — traffic-light severity."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import InverterAdapter
from app.adapters.factory import get_adapter
from app.db.models import MetricSampleRow
from app.schemas.domain import (
    HistoryRange,
    SystemWarning,
    SystemWarningSeverity,
    SystemWarningsResponse,
)
from app.services.analytics_helpers import integrate_kwh, range_start
from app.services.charge_window_service import charge_window_service
from app.services.iog_schedule import time_to_minutes
from app.services.tariff_clock import tariff_now, to_tariff
from app.services.tariff_service import tariff_service

_IMPORT_SUSTAINED_SAMPLES = 6
_HIGH_SOC_DEFAULT = 95.0


def _minute_in_peak(minute: int, peak_start: str, peak_end: str) -> bool:
    start = time_to_minutes(peak_start)
    end = time_to_minutes(peak_end)
    if start <= end:
        return start <= minute < end
    return minute >= start or minute < end


class SystemWarningsService:
    async def evaluate(
        self,
        db: AsyncSession,
        *,
        adapter: InverterAdapter | None = None,
    ) -> SystemWarningsResponse:
        adapter = adapter or get_adapter()
        tariff = await tariff_service.get_tariff(db)
        warnings: list[SystemWarning] = []

        metrics = None
        try:
            metrics = await adapter.get_live_metrics()
        except Exception:
            pass

        window = await charge_window_service.get_status(adapter)

        start = range_start(HistoryRange.DAY)
        result = await db.execute(
            select(MetricSampleRow)
            .where(MetricSampleRow.timestamp >= start)
            .order_by(MetricSampleRow.timestamp.asc())
        )
        rows = list(result.scalars().all())

        import_kwh = integrate_kwh(rows, "grid_import_w")
        pv_kwh = integrate_kwh(rows, "pv_power_w")
        consumption_kwh = integrate_kwh(rows, "house_load_w")

        soc_threshold = float(tariff.warning_battery_soc_threshold_pct)
        import_threshold = float(tariff.warning_import_threshold_w)

        soc = metrics.battery_soc_pct if metrics else window.battery_soc_pct
        grid_import = metrics.grid_import_w if metrics else window.grid_import_w
        grid_export = metrics.grid_export_w if metrics else 0.0

        if self._sustained_high_soc_import(rows, soc_threshold, import_threshold):
            warnings.append(
                SystemWarning(
                    id="battery_not_discharging",
                    severity=SystemWarningSeverity.RED,
                    title="Battery may not be discharging",
                    message=(
                        "Grid import occurred while battery SOC was high. "
                        "Check discharge settings or reserve SOC."
                    ),
                    category="battery",
                )
            )

        now_local = tariff_now()
        minute = now_local.hour * 60 + now_local.minute
        if (
            _minute_in_peak(minute, tariff.peak_start, tariff.peak_end)
            and grid_import > import_threshold
            and soc > tariff.battery_minimum_reserve_pct + 5
        ):
            warnings.append(
                SystemWarning(
                    id="peak_rate_import",
                    severity=SystemWarningSeverity.AMBER,
                    title="Peak-rate import detected",
                    message=(
                        f"Importing {grid_import:.0f} W during peak rate while battery "
                        f"is at {soc:.0f}% (above minimum reserve)."
                    ),
                    category="import",
                )
            )

        charge_kwh = rows[-1].daily_battery_charge_kwh if rows else 0.0
        discharge_kwh = rows[-1].daily_battery_discharge_kwh if rows else 0.0
        charge_kwh = charge_kwh or 0.0
        discharge_kwh = discharge_kwh or 0.0
        if charge_kwh > 2.0 and discharge_kwh < 0.5 and import_kwh > 1.0:
            warnings.append(
                SystemWarning(
                    id="poor_battery_utilisation",
                    severity=SystemWarningSeverity.AMBER,
                    title="Battery charged but barely used",
                    message=(
                        "Battery charged overnight but was not significantly used during the day."
                    ),
                    category="battery",
                )
            )

        if (
            grid_export > import_threshold
            and soc < tariff.maximum_charge_pct - 10
            and import_kwh > 0.5
        ):
            warnings.append(
                SystemWarning(
                    id="export_with_battery_room",
                    severity=SystemWarningSeverity.AMBER,
                    title="Solar exported when battery had room",
                    message=(
                        "Solar may have been exported when it could have been stored "
                        "for later use."
                    ),
                    category="export",
                )
            )

        if grid_import > import_threshold and grid_export > import_threshold:
            warnings.append(
                SystemWarning(
                    id="simultaneous_import_export",
                    severity=SystemWarningSeverity.AMBER,
                    title="Import and export at the same time",
                    message=(
                        "Import/export readings may be inconsistent. "
                        "Check data source alignment."
                    ),
                    category="data",
                )
            )

        avg_soc = sum(r.battery_soc_pct for r in rows) / len(rows) if rows else soc
        if avg_soc > _HIGH_SOC_DEFAULT and import_kwh > 1.0:
            warnings.append(
                SystemWarning(
                    id="battery_too_full",
                    severity=SystemWarningSeverity.AMBER,
                    title="Battery reserve may be too restrictive",
                    message=(
                        f"Battery averaged {avg_soc:.0f}% while {import_kwh:.1f} kWh "
                        "was imported from the grid."
                    ),
                    category="battery",
                )
            )

        if rows:
            peak_rows = [
                r
                for r in rows
                if _minute_in_peak(
                    to_tariff(r.timestamp).hour * 60 + to_tariff(r.timestamp).minute,
                    tariff.peak_start,
                    tariff.peak_end,
                )
            ]
            if peak_rows:
                early_low = any(
                    r.battery_soc_pct <= tariff.battery_minimum_reserve_pct + 2
                    for r in peak_rows[: len(peak_rows) // 2]
                )
                late_import = any(
                    r.grid_import_w > import_threshold
                    for r in peak_rows[len(peak_rows) // 2 :]
                )
                if early_low and late_import:
                    warnings.append(
                        SystemWarning(
                            id="battery_emptied_early",
                            severity=SystemWarningSeverity.AMBER,
                            title="Battery discharged too early",
                            message=(
                                "Battery reached minimum reserve early and peak import "
                                "followed later. A later discharge window may save more."
                            ),
                            category="battery",
                        )
                    )

        if pv_kwh > 10 and import_kwh > pv_kwh * 0.5:
            warnings.append(
                SystemWarning(
                    id="high_solar_low_savings",
                    severity=SystemWarningSeverity.AMBER,
                    title="High solar but limited savings",
                    message=(
                        "Solar generation was high, but savings were limited. "
                        "Possible causes: high export, low self-consumption, or battery settings."
                    ),
                    category="solar",
                )
            )

        headline = self._status_headline(warnings, pv_kwh, import_kwh, consumption_kwh)
        return SystemWarningsResponse(warnings=warnings, status_headline=headline)

    @staticmethod
    def _sustained_high_soc_import(
        rows: list[MetricSampleRow],
        soc_threshold: float,
        import_threshold: float,
    ) -> bool:
        streak = 0
        for row in rows:
            if (
                row.battery_soc_pct >= soc_threshold
                and row.grid_import_w >= import_threshold
            ):
                streak += 1
                if streak >= _IMPORT_SUSTAINED_SAMPLES:
                    return True
            else:
                streak = 0
        return False

    @staticmethod
    def _status_headline(
        warnings: list[SystemWarning],
        pv_kwh: float,
        import_kwh: float,
        consumption_kwh: float,
    ) -> str:
        red = [w for w in warnings if w.severity == SystemWarningSeverity.RED]
        amber = [w for w in warnings if w.severity == SystemWarningSeverity.AMBER]
        if red:
            return red[0].title + " — " + red[0].message.split(".")[0] + "."
        if amber:
            return "Warning — " + amber[0].message.split(".")[0] + "."
        if pv_kwh > 1 and import_kwh < consumption_kwh * 0.3:
            return "Good — most daytime electricity came from solar/battery."
        return "System operating normally."


system_warnings_service = SystemWarningsService()
