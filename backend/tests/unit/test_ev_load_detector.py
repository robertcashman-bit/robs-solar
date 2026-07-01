"""Unit tests for EV load heuristic detector."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.schemas.domain import DispatchWindow, LiveMetrics
from app.services.ev_load_detector import EvLoadDetector


def _metrics(load_w: float, *, grid_import_w: Optional[float] = None) -> LiveMetrics:
    import_w = grid_import_w if grid_import_w is not None else load_w
    return LiveMetrics(
        pv_power_w=0,
        battery_soc_pct=50,
        house_load_w=load_w,
        grid_import_w=import_w,
        grid_export_w=0,
        inverter_mode="self_use",
        inverter_status="online",
        daily_pv_kwh=0,
        daily_import_kwh=0,
        daily_export_kwh=0,
        timestamp=datetime.now(timezone.utc),
    )


def test_ev_not_detected_outside_dispatch() -> None:
    detector = EvLoadDetector()
    detector.update(_metrics(5000), planned=[])
    assert detector.car_charging_likely is False


def test_ev_detected_sustained_high_load_in_dispatch() -> None:
    detector = EvLoadDetector()
    now = datetime.now(timezone.utc)
    planned = [
        DispatchWindow(
            start=now - timedelta(minutes=10),
            end=now + timedelta(hours=2),
            source="test",
        )
    ]
    for seconds_ago in (120, 60, 0):
        metrics = _metrics(4500)
        metrics.timestamp = now - timedelta(seconds=seconds_ago)
        detector.update(metrics, planned=planned)
    assert detector.car_charging_likely is True


def test_ev_detected_via_grid_import_when_load_ct_low() -> None:
    detector = EvLoadDetector()
    now = datetime.now(timezone.utc)
    planned = [
        DispatchWindow(
            start=now - timedelta(minutes=10),
            end=now + timedelta(hours=2),
            source="test",
        )
    ]
    for seconds_ago in (120, 60, 0):
        metrics = _metrics(250, grid_import_w=7200)
        metrics.timestamp = now - timedelta(seconds=seconds_ago)
        detector.update(metrics, planned=planned)
    assert detector.car_charging_likely is True
