"""Integration provider base classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IntegrationNotConfiguredError(Exception):
    """Raised when an integration is not yet set up."""


class BaseFinanceProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def sync_accounts(self) -> list[dict[str, Any]]:
        """Return normalized account records for import."""

    @abstractmethod
    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        """Return normalized transaction records."""


class ManualFinanceProvider(BaseFinanceProvider):
    name = "manual"

    async def sync_accounts(self) -> list[dict[str, Any]]:
        return []

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        return []


class OpenBankingProvider(BaseFinanceProvider):
    name = "open_banking"

    async def sync_accounts(self) -> list[dict[str, Any]]:
        raise IntegrationNotConfiguredError(
            "Open Banking is not configured. Connect a provider in Settings when available."
        )

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        raise IntegrationNotConfiguredError("Open Banking is not configured.")


class QuickFileProvider(BaseFinanceProvider):
    name = "quickfile"

    async def sync_accounts(self) -> list[dict[str, Any]]:
        raise IntegrationNotConfiguredError(
            "QuickFile API is not configured. Add QUICKFILE credentials in Settings when available."
        )

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        raise IntegrationNotConfiguredError("QuickFile API is not configured.")


class TeslaProvider(BaseFinanceProvider):
    name = "tesla"

    async def sync_accounts(self) -> list[dict[str, Any]]:
        raise IntegrationNotConfiguredError("Tesla API integration is not yet available.")

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        raise IntegrationNotConfiguredError("Tesla API integration is not yet available.")
