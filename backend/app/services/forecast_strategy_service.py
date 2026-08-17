"""Structured tomorrow's strategy from forecast + tariff + battery state."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.domain import ForecastStrategy
from app.services.forecast_service import forecast_service
from app.services.tariff_clock import tariff_now
from app.services.tariff_service import tariff_service


class ForecastStrategyService:
    async def get_strategy(
        self,
        db: AsyncSession,
        *,
        solar_level: str = "medium",
    ) -> ForecastStrategy:
        tariff = await tariff_service.get_tariff(db)
        tomorrow = (tariff_now() + timedelta(days=1)).strftime("%Y-%m-%d")

        predicted = 0.0
        try:
            forecast = await forecast_service.get_forecast(days=3)
            points = forecast.get("points") or []
            if len(points) > 1:
                predicted = float(points[1].get("predicted_kwh") or 0)
        except Exception:
            pass

        level = solar_level.lower()
        if level == "high" or predicted > 15:
            return ForecastStrategy(
                date=tomorrow,
                solar_level="high",
                overnight_charge_target_pct=70,
                daytime_reserve_pct=tariff.battery_minimum_reserve_pct,
                fill_battery_overnight=False,
                prioritise_self_consumption=True,
                headline="High solar day — leave room for PV",
                detail=(
                    "Tomorrow looks like a high solar day. Avoid overcharging overnight "
                    "so there is room for solar generation."
                ),
                predicted_solar_kwh=predicted,
            )
        if level == "low" or predicted < 5:
            return ForecastStrategy(
                date=tomorrow,
                solar_level="low",
                overnight_charge_target_pct=tariff.maximum_charge_pct,
                daytime_reserve_pct=tariff.battery_minimum_reserve_pct,
                fill_battery_overnight=True,
                prioritise_self_consumption=True,
                headline="Low solar day — fill battery overnight",
                detail=(
                    f"Tomorrow looks like a low solar day. Charge battery to "
                    f"{tariff.maximum_charge_pct}% overnight and allow discharge to "
                    f"{tariff.battery_minimum_reserve_pct}% from {tariff.peak_start}."
                ),
                predicted_solar_kwh=predicted,
            )

        return ForecastStrategy(
            date=tomorrow,
            solar_level="medium",
            overnight_charge_target_pct=85,
            daytime_reserve_pct=tariff.battery_minimum_reserve_pct,
            fill_battery_overnight=True,
            prioritise_self_consumption=True,
            headline="Moderate solar — balanced overnight charge",
            detail=(
                f"Charge to ~85% overnight ({tariff.off_peak_start}–{tariff.off_peak_end}), "
                f"discharge to {tariff.battery_minimum_reserve_pct}% during the day."
            ),
            predicted_solar_kwh=predicted,
        )


forecast_strategy_service = ForecastStrategyService()
