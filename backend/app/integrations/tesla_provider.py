"""Tesla provider — EV charging visibility."""

from __future__ import annotations

from typing import Any

from app.integrations.base import BaseFinanceProvider, IntegrationNotConfiguredError
from app.integrations.tesla_client import TeslaClient, TeslaError
from app.schemas.finance import TeslaChargingStatus, TeslaConfig


class TeslaProvider(BaseFinanceProvider):
    name = "tesla"

    def __init__(self, config: TeslaConfig) -> None:
        self._config = config
        self._client = TeslaClient(config)

    def _ensure_configured(self) -> None:
        if not self._client.configured:
            raise IntegrationNotConfiguredError(
                "Tesla is not configured. Set TESLA_* credentials in Settings."
            )

    async def sync_accounts(self) -> list[dict[str, Any]]:
        return []

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        return []

    async def get_charging_status(self) -> TeslaChargingStatus:
        self._ensure_configured()
        try:
            if self._config.energy_site_id:
                live = await self._client.get_energy_live_status(self._config.energy_site_id)
                power = (
                    live.get("solar_power")
                    or live.get("battery_power")
                    or live.get("load_power")
                )
                return TeslaChargingStatus(
                    connected=True,
                    energy_site_id=self._config.energy_site_id,
                    charger_power_kw=round(float(power) / 1000, 2) if power is not None else None,
                    message="Energy site live status",
                )

            vehicles = await self._client.list_vehicles()
            if not vehicles:
                return TeslaChargingStatus(connected=False, message="No Tesla vehicles found")
            vehicle = vehicles[0]
            vehicle_id = str(vehicle.get("id") or vehicle.get("id_s") or "")
            name = str(vehicle.get("display_name") or vehicle.get("vin") or "Tesla")
            data = await self._client.get_vehicle_data(vehicle_id)
            charge = data.get("charge_state", {})
            return TeslaChargingStatus(
                connected=True,
                vehicle_name=name,
                charging_state=str(charge.get("charging_state") or "Unknown"),
                battery_level_pct=_float_or_none(charge.get("battery_level")),
                charge_limit_pct=_float_or_none(charge.get("charge_limit_soc")),
                charger_power_kw=_float_or_none(charge.get("charger_power")),
                message="Vehicle charging status",
            )
        except TeslaError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc

    async def test_connection(self) -> dict[str, Any]:
        status = await self.get_charging_status()
        return {
            "ok": status.connected,
            "vehicle_name": status.vehicle_name,
            "charging_state": status.charging_state,
        }


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
