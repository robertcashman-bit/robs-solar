"""Short-lived cache for live inverter metrics — avoids duplicate Sunsynk polls."""

from __future__ import annotations

from datetime import datetime, timezone

from app.adapters.base import InverterAdapter
from app.schemas.domain import LiveMetrics
from app.services.effective_load import finalize_live_metrics

_CACHE_TTL_SECONDS = 8.0


class LiveMetricsCache:
    def __init__(self) -> None:
        self._metrics: LiveMetrics | None = None
        self._fetched_at: datetime | None = None

    def _fresh(self) -> bool:
        if self._metrics is None or self._fetched_at is None:
            return False
        age = (datetime.now(timezone.utc) - self._fetched_at).total_seconds()
        return age < _CACHE_TTL_SECONDS

    def peek(self) -> LiveMetrics | None:
        return self._metrics if self._fresh() else None

    @property
    def fetched_at(self) -> datetime | None:
        """When the cached snapshot was captured (regardless of TTL freshness)."""
        return self._fetched_at

    def age_seconds(self) -> float | None:
        """Age of the cached snapshot in seconds, or None if nothing cached yet."""
        if self._fetched_at is None:
            return None
        return (datetime.now(timezone.utc) - self._fetched_at).total_seconds()

    async def get(self, adapter: InverterAdapter) -> LiveMetrics:
        cached = self.peek()
        if cached is not None:
            return cached
        metrics = await adapter.get_live_metrics()
        self._metrics = finalize_live_metrics(metrics)
        self._fetched_at = datetime.now(timezone.utc)
        return self._metrics


live_metrics_cache = LiveMetricsCache()
