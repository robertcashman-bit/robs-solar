"""Detect simulator-shaped metrics when the backend is configured for live data."""

from __future__ import annotations

from app.config import settings
from app.schemas.domain import ConnectivityStatus, InverterSettingsResponse, LiveMetrics
from app.services.data_source import is_live_mode

_SIMULATOR_SN = "SIM-0001"
_SIMULATOR_PLANT = "sim-plant"


class LiveMetricsGuardError(Exception):
    """Live adapter mode received simulator-shaped readings."""


def assert_live_metrics_integrity(
    metrics: LiveMetrics,
    *,
    connectivity: ConnectivityStatus | None = None,
    settings_payload: InverterSettingsResponse | None = None,
) -> None:
    if not is_live_mode():
        return

    if connectivity is not None and connectivity.adapter_mode == "simulator":
        raise LiveMetricsGuardError(
            "Adapter connectivity reports simulator mode while ADAPTER_MODE is live."
        )

    if settings_payload is not None:
        if settings_payload.inverter_sn == _SIMULATOR_SN:
            raise LiveMetricsGuardError(
                "Inverter serial indicates simulator data (SIM-0001) in live mode."
            )
        if settings_payload.plant_id == _SIMULATOR_PLANT:
            raise LiveMetricsGuardError(
                "Plant id indicates simulator data (sim-plant) in live mode."
            )

    if settings.adapter_mode.lower() == "simulator":
        raise LiveMetricsGuardError("ADAPTER_MODE is simulator but live metrics were requested.")
