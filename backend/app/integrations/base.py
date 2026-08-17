"""Integration provider base classes — BankProvider surface for statement sync."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IntegrationNotConfiguredError(Exception):
    """Raised when an integration is not yet set up."""


class BaseFinanceProvider(ABC):
    """Canonical provider interface (also referred to as BankProvider).

    Concrete providers implement account/transaction sync. CSV/OFX imports use the
    statement parser path instead of inventing a fake live bank API.
    """

    name: str = "base"

    async def connect(self) -> dict[str, Any]:
        """Optional connection handshake. Default: already connected for local providers."""
        return {"connected": True, "provider": self.name}

    async def disconnect(self) -> dict[str, Any]:
        return {"connected": False, "provider": self.name}

    async def get_accounts(self) -> list[dict[str, Any]]:
        return await self.sync_accounts()

    async def get_balances(self) -> list[dict[str, Any]]:
        accounts = await self.sync_accounts()
        return [
            {
                "id": item.get("external_id") or item.get("id"),
                "name": item.get("name"),
                "balance_gbp": item.get("balance_gbp"),
                "currency": item.get("currency") or "GBP",
            }
            for item in accounts
        ]

    async def get_transactions(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> list[dict[str, Any]]:
        rows = await self.sync_transactions(since=start_date)
        if end_date:
            rows = [
                row
                for row in rows
                if str(row.get("posted_on") or row.get("date") or "") <= end_date
            ]
        return rows

    async def refresh_transactions(self) -> list[dict[str, Any]]:
        return await self.sync_transactions(since=None)

    @abstractmethod
    async def sync_accounts(self) -> list[dict[str, Any]]:
        """Return normalized account records for import."""

    @abstractmethod
    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        """Return normalized transaction records."""


# Alias matching the product brief naming.
BankProvider = BaseFinanceProvider


class ManualFinanceProvider(BaseFinanceProvider):
    name = "manual"

    async def sync_accounts(self) -> list[dict[str, Any]]:
        return []

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        return []


class CsvFinanceProvider(BaseFinanceProvider):
    """Marker provider — actual CSV/OFX ingestion is via statement_parsers + import API."""

    name = "csv"

    async def sync_accounts(self) -> list[dict[str, Any]]:
        return []

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        raise IntegrationNotConfiguredError(
            "Upload a CSV, OFX, QFX or QIF statement on Finance → Import. "
            "There is no live scrape of online banking."
        )


class OpenBankingProvider(BaseFinanceProvider):
    name = "open_banking"

    async def sync_accounts(self) -> list[dict[str, Any]]:
        raise IntegrationNotConfiguredError(
            "Open Banking is not configured. Connect a provider in Settings when available."
        )

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        raise IntegrationNotConfiguredError("Open Banking is not configured.")


class TeslaProvider(BaseFinanceProvider):
    name = "tesla"

    async def sync_accounts(self) -> list[dict[str, Any]]:
        raise IntegrationNotConfiguredError("Tesla API integration is not yet available.")

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        raise IntegrationNotConfiguredError("Tesla API integration is not yet available.")
