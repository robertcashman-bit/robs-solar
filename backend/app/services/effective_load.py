"""Shared house-load resolution for Sunsynk metrics and EV heuristics."""

from __future__ import annotations

from app.schemas.domain import HouseLoadSource, LiveMetrics

POWER_NOISE_FLOOR_W = 5.0
UNDERREPORTED_SLACK_W = 500.0


def derived_house_load(
    *,
    pv: float,
    grid_import: float,
    grid_export: float,
    battery_power_w: float,
) -> float:
    return pv + grid_import - grid_export + battery_power_w


def resolve_house_load(
    reported: float,
    *,
    pv: float,
    grid_import: float,
    grid_export: float,
    battery_power_w: float,
) -> tuple[float, HouseLoadSource]:
    """Use Sunsynk load CT when plausible; else derive from instantaneous balance."""
    floor = POWER_NOISE_FLOOR_W
    derived = derived_house_load(
        pv=pv,
        grid_import=grid_import,
        grid_export=grid_export,
        battery_power_w=battery_power_w,
    )
    if reported > floor:
        if derived > reported + UNDERREPORTED_SLACK_W and derived > floor:
            return derived, HouseLoadSource.DERIVED
        return reported, HouseLoadSource.REPORTED
    if derived > floor:
        return derived, HouseLoadSource.DERIVED
    return max(0.0, reported), HouseLoadSource.MINIMAL


def effective_load_w(metrics: LiveMetrics, *, in_cheap_window: bool = False) -> float:
    """Best load signal for EV detection — includes off-CT draw visible on grid import."""
    load = metrics.house_load_w
    if in_cheap_window and metrics.grid_import_w > load:
        return metrics.grid_import_w
    return load


def finalize_live_metrics(metrics: LiveMetrics) -> LiveMetrics:
    """Ensure house load and source reflect the power balance when the CT reads zero."""
    battery = metrics.battery_power_w or 0.0
    derived = derived_house_load(
        pv=metrics.pv_power_w,
        grid_import=metrics.grid_import_w,
        grid_export=metrics.grid_export_w,
        battery_power_w=battery,
    )
    if metrics.house_load_w > POWER_NOISE_FLOOR_W or derived <= 0:
        return metrics
    return metrics.model_copy(
        update={
            "house_load_w": round(derived, 1),
            "house_load_source": HouseLoadSource.DERIVED,
        }
    )
