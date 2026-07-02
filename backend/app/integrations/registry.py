"""Integration provider registry."""

from __future__ import annotations

from app.integrations.base import (
    BaseFinanceProvider,
    ManualFinanceProvider,
    OpenBankingProvider,
    QuickFileProvider,
    TeslaProvider,
)


class IntegrationRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseFinanceProvider] = {
            "manual": ManualFinanceProvider(),
            "open_banking": OpenBankingProvider(),
            "quickfile": QuickFileProvider(),
            "tesla": TeslaProvider(),
        }

    def get(self, name: str) -> BaseFinanceProvider:
        return self._providers.get(name, self._providers["manual"])

    def list_providers(self) -> list[dict[str, str]]:
        return [
            {"id": "manual", "label": "Manual entry", "status": "active"},
            {"id": "open_banking", "label": "Open Banking", "status": "coming_soon"},
            {"id": "quickfile", "label": "QuickFile", "status": "coming_soon"},
            {"id": "octopus", "label": "Octopus Energy", "status": "active"},
            {"id": "sunsynk", "label": "Sunsynk Connect", "status": "active"},
            {"id": "tesla", "label": "Tesla", "status": "coming_soon"},
        ]


integration_registry = IntegrationRegistry()
