"""Integration provider registry."""

from __future__ import annotations

from app.integrations.base import (
    BaseFinanceProvider,
    ManualFinanceProvider,
)


class IntegrationRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseFinanceProvider] = {
            "manual": ManualFinanceProvider(),
        }

    def get(self, name: str) -> BaseFinanceProvider:
        return self._providers.get(name, self._providers["manual"])

    def list_providers(self) -> list[dict[str, str]]:
        return [
            {"id": "manual", "label": "Manual entry", "status": "active"},
            {"id": "open_banking", "label": "Open Banking", "status": "inactive"},
            {"id": "lunchflow", "label": "Lunch Flow", "status": "inactive"},
            {"id": "funding_circle", "label": "Funding Circle", "status": "inactive"},
            {"id": "quickfile", "label": "QuickFile", "status": "inactive"},
        ]


integration_registry = IntegrationRegistry()
