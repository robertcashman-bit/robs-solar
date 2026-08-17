"""TrueLayer Open Banking provider."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.integrations.base import BaseFinanceProvider, IntegrationNotConfiguredError
from app.integrations.truelayer_client import TrueLayerClient, TrueLayerError
from app.schemas.finance import FinanceAccountType, FinanceScope, TrueLayerConfig

_BUSINESS_MARKERS = ("business", "ltd", "limited", "company", "llp", "plc")


def _map_account_type(account_type: str) -> FinanceAccountType:
    value = (account_type or "").upper()
    if "CREDIT" in value or "CARD" in value:
        return FinanceAccountType.CREDIT_CARD
    if "MORTGAGE" in value:
        return FinanceAccountType.MORTGAGE
    if "LOAN" in value:
        return FinanceAccountType.LOAN
    return FinanceAccountType.CURRENT


def _signed_amount(item: dict[str, Any]) -> float:
    raw = item.get("amount")
    try:
        amount = float(raw or 0)
    except (TypeError, ValueError):
        return 0.0
    tx_type = str(item.get("transaction_type") or item.get("type") or "").lower()
    if amount < 0:
        return amount
    if tx_type in {"debit", "outflow"}:
        return -abs(amount)
    if tx_type in {"credit", "inflow"}:
        return abs(amount)
    return amount


def infer_account_scope(display_name: str, provider_name: str = "") -> FinanceScope:
    text = f"{display_name} {provider_name}".lower()
    if any(marker in text for marker in _BUSINESS_MARKERS):
        return FinanceScope.BUSINESS
    return FinanceScope.PERSONAL


class TrueLayerProvider(BaseFinanceProvider):
    name = "open_banking"

    def __init__(self, config: TrueLayerConfig, *, access_token: str = "") -> None:
        self._config = config
        self._client = TrueLayerClient(config, access_token=access_token)

    def _ensure_configured(self) -> None:
        if not self._client.configured:
            raise IntegrationNotConfiguredError(
                "Open Banking is not configured. Set TrueLayer credentials in Settings."
            )

    async def sync_accounts(self) -> list[dict[str, Any]]:
        self._ensure_configured()
        try:
            accounts = await self._client.fetch_accounts()
        except TrueLayerError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc

        normalized: list[dict[str, Any]] = []
        for record in accounts:
            account_id = str(record.get("account_id") or record.get("accountId") or "")
            if not account_id:
                continue
            try:
                balance = await self._client.fetch_balance(account_id)
            except TrueLayerError:
                balance = 0.0
            display_name = str(
                record.get("display_name")
                or record.get("displayName")
                or record.get("description")
                or "Bank account"
            )
            provider_name = str(record.get("provider", {}).get("display_name", "Open Banking"))
            raw_type = str(record.get("account_type") or record.get("accountType") or "")
            mapped = _map_account_type(raw_type)
            normalized.append(
                {
                    "scope": infer_account_scope(display_name, provider_name).value,
                    "account_type": mapped.value,
                    "name": display_name,
                    "provider": provider_name,
                    "balance_gbp": round(balance, 2),
                    "external_id": account_id,
                    "notes": "Synced via TrueLayer Open Banking",
                }
            )
        try:
            cards = await self._client.fetch_cards()
        except TrueLayerError:
            cards = []
        for record in cards:
            card_id = str(record.get("account_id") or record.get("card_id") or "")
            if not card_id:
                continue
            try:
                card_balance = await self._client.fetch_card_balance(card_id)
            except TrueLayerError:
                card_balance = {"current": 0.0, "credit_limit": None}
            display_name = str(record.get("display_name") or record.get("name_on_card") or "Card")
            provider_name = str(record.get("provider", {}).get("display_name", "Open Banking"))
            raw_type = str(record.get("card_type") or record.get("account_type") or "CREDIT")
            normalized.append(
                {
                    "scope": infer_account_scope(display_name, provider_name).value,
                    "account_type": _map_account_type(raw_type).value,
                    "name": display_name,
                    "provider": provider_name,
                    "balance_gbp": round(float(card_balance.get("current") or 0), 2),
                    "credit_limit_gbp": card_balance.get("credit_limit"),
                    "external_id": card_id,
                    "notes": "Synced via TrueLayer Open Banking",
                }
            )
        return normalized

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        self._ensure_configured()
        days = 365
        if since:
            try:
                start = datetime.fromisoformat(since[:10]).date()
                days = max(1, (datetime.now(timezone.utc).date() - start).days)
            except ValueError:
                days = 365
        try:
            raw = await self._client.fetch_recent_transactions(days=days)
        except TrueLayerError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
        collected: list[dict[str, Any]] = []
        for item in raw:
            amount = _signed_amount(item)
            if amount == 0:
                continue
            dated = str(item.get("timestamp") or item.get("date") or "")[:10]
            collected.append(
                {
                    "amount_gbp": round(amount, 2),
                    "date": dated,
                    "posted_on": dated,
                    "description": str(
                        item.get("description") or item.get("merchant_name") or ""
                    ),
                    "external_id": str(
                        item.get("transaction_id") or item.get("transactionId") or ""
                    )
                    or None,
                    "account_external_id": str(
                        item.get("account_id") or item.get("accountId") or ""
                    ),
                    "account_name": str(item.get("account_name") or ""),
                    "currency": str(item.get("currency") or "GBP"),
                    "scope": infer_account_scope(
                        str(item.get("account_name") or ""),
                        str(item.get("provider") or ""),
                    ).value,
                }
            )
        return collected

    async def summarise_recent_activity(self) -> tuple[float, float]:
        """Last 30-day income/spend from Open Banking transactions."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
        transactions = await self.sync_transactions(since=cutoff)
        income = sum(item["amount_gbp"] for item in transactions if item["amount_gbp"] > 0)
        spending = sum(-item["amount_gbp"] for item in transactions if item["amount_gbp"] < 0)
        return round(income, 2), round(spending, 2)

    async def test_connection(self) -> dict[str, Any]:
        self._ensure_configured()
        try:
            accounts = await self._client.fetch_accounts()
        except TrueLayerError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
        return {"ok": True, "account_count": len(accounts)}
