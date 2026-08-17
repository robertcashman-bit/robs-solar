"""Heuristic EV load detection during IOG cheap windows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import settings
from app.schemas.domain import DispatchWindow, EvStatusResponse, LiveMetrics
from app.services.effective_load import effective_load_w
from app.services.iog_schedule import charge_intervals_from_windows, is_charge_minute

_LOAD_THRESHOLD_W = 4000
_SUSTAINED_SECONDS = 120


@dataclass
class _LoadSample:
    timestamp: datetime
    signal_w: float


@dataclass
class EvLoadDetector:
    _samples: list[_LoadSample] = field(default_factory=list)
    _car_charging_likely: bool = False
    _in_dispatch: bool = False

    def _prune(self, now: datetime) -> None:
        cutoff = now.timestamp() - _SUSTAINED_SECONDS
        self._samples = [s for s in self._samples if s.timestamp.timestamp() >= cutoff]

    def _in_cheap_window(self, now: datetime, planned: list[DispatchWindow]) -> bool:
        charge = charge_intervals_from_windows(
            settings.iog_offpeak_start,
            settings.iog_offpeak_end,
            planned,
            now=now,
        )
        from app.services.tariff_clock import to_tariff

        local = to_tariff(now)
        minute = local.hour * 60 + local.minute
        return is_charge_minute(minute, charge)

    def update(self, metrics: LiveMetrics, planned: list[DispatchWindow] | None = None) -> None:
        now = metrics.timestamp or datetime.now(timezone.utc)
        self._prune(now)
        planned = planned or []
        self._in_dispatch = self._in_cheap_window(now, planned)
        signal = effective_load_w(metrics, in_cheap_window=self._in_dispatch)
        self._samples.append(_LoadSample(timestamp=now, signal_w=signal))

        if not self._in_dispatch:
            self._car_charging_likely = False
            return

        if len(self._samples) < 2:
            self._car_charging_likely = False
            return

        span = (self._samples[-1].timestamp - self._samples[0].timestamp).total_seconds()
        if span < _SUSTAINED_SECONDS:
            self._car_charging_likely = False
            return

        high_load = all(s.signal_w > _LOAD_THRESHOLD_W for s in self._samples)
        self._car_charging_likely = high_load

    @property
    def car_charging_likely(self) -> bool:
        return self._car_charging_likely

    def status(self, metrics: LiveMetrics | None = None) -> EvStatusResponse:
        load = metrics.house_load_w if metrics else (
            self._samples[-1].signal_w if self._samples else 0.0
        )
        message = ""
        if self._car_charging_likely:
            message = "Sustained high load during cheap window — EV charging likely"
        elif self._in_dispatch:
            message = "In cheap window"
        return EvStatusResponse(
            car_charging_likely=self._car_charging_likely,
            in_dispatch_window=self._in_dispatch,
            house_load_w=load,
            message=message,
        )


ev_load_detector = EvLoadDetector()


async def sync_ev_detector(metrics: LiveMetrics) -> None:
    """Refresh EV heuristics from a live metrics snapshot."""
    planned: list[DispatchWindow] = []
    try:
        from app.services.octopus_client import octopus_client

        dispatches = await octopus_client.get_dispatches()
        planned = list(dispatches.planned)
    except Exception:
        pass
    ev_load_detector.update(metrics, planned)
