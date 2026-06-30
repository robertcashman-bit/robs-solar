"""Solar generation forecast via Open-Meteo (free, no API key)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"


class SolarForecastService:
    async def get_forecast(self, days: int = 3) -> dict[str, Any]:
        params = {
            "latitude": settings.forecast_latitude,
            "longitude": settings.forecast_longitude,
            "daily": "shortwave_radiation_sum",
            "timezone": "Europe/London",
            "forecast_days": days,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(OPEN_METEO, params=params)
            response.raise_for_status()
            data = response.json()

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        radiation = daily.get("shortwave_radiation_sum", [])
        total_w = settings.panel_count_ew + settings.panel_count_w
        peak_kw = total_w * settings.panel_wattage / 1000

        points = []
        for date, mj in zip(dates, radiation):
            # Rough yield: MJ/m²/day * system efficiency * array factor
            predicted_kwh = max(0.0, mj * 0.15 * (peak_kw / 10.56))
            points.append({"date": date, "predicted_kwh": round(predicted_kwh, 2)})

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "location": {"lat": settings.forecast_latitude, "lon": settings.forecast_longitude},
            "panel_config": {
                "ew_panels": settings.panel_count_ew,
                "w_panels": settings.panel_count_w,
                "wattage": settings.panel_wattage,
            },
            "days": points,
            "hint": (
                "If tomorrow's forecast exceeds 15 kWh, defer overnight grid charging."
                if points and len(points) > 1 and points[1]["predicted_kwh"] > 15
                else None
            ),
        }


forecast_service = SolarForecastService()
