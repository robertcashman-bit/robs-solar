"""Lunch Flow Open Banking provider."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.integrations.base import BaseFinanceProvider, IntegrationNotConfiguredError
from app.integrations.lunchflow_client import LunchFlowClient, LunchFlowError
from app.schemas.finance import FinanceAccountType, FinanceScope, LunchFlowConfig
from app.services.finance.lunchflow_scope import (
    credit_card_balance_gbp,
    infer_lunchflow_scope,
    parse_business_connection_ids,
)


def _map_account_type(account_type: str, name: str = "") -> FinanceAccountType:
    value = f"{account_type} {name}".upper()
    if "CREDIT" in value or "CARD" in value:
        return FinanceAccountType.CREDIT_CARD
    if "LOAN" in value or "MORTGAGE" in value:
        return FinanceAccountType.LOAN
    return FinanceAccountType.CURRENT


def _optional_amount(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        value = value.get("amount")
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    return round(amount, 2)


_DATE_KEYS = (
    "date",
    "valueDate",
    "transactionDate",
    "bookingDate",
    "timestamp",
    "posted_on",
    "booking_date",
    "value_date",
    "transaction_date",
)


def _transaction_date(item: dict[str, Any]) -> str:
    """Pick the first usable ISO date from known Lunch Flow / OB keys.

    Empty provider strings are skipped — never invent a date.
    """
    for key in _DATE_KEYS:
        raw = item.get(key)
        if raw is None or raw == "":
            continue
        text = str(raw).strip()
        if not text:
            continue
        # ISO date or datetime: YYYY-MM-DD...
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            candidate = text[:10]
            try:
                datetime.fromisoformat(candidate)
            except ValueError:
                continue
            return candidate
    return ""


def _transaction_amount(item: dict[str, Any]) -> float:
    amount = item.get("amount")
    if isinstance(amount, dict):
        amount = amount.get("amount")
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        return 0.0
    direction = str(item.get("type") or item.get("direction") or item.get("side") or "").lower()
    if direction in {"debit", "outflow", "expense", "out"}:
        return -abs(value)
    if direction in {"credit", "inflow", "income", "in"}:
        return abs(value)
    return value


def _normalize_transaction(
    item: dict[str, Any], cutoff: str, *, account_name: str = ""
) -> dict[str, Any] | None:
    if item.get("isPending") is True:
        return None
    dated = _transaction_date(item)
    if dated and dated < cutoff:
        return None
    amount = _transaction_amount(item)
    if amount == 0:
        return None
    description = str(
        item.get("description")
        or item.get("merchant")
        or item.get("name")
        or item.get("narrative")
        or ""
    )[:256]
    external_id = str(
        item.get("id") or item.get("transactionId") or item.get("transaction_id") or ""
    )
    currency = str(item.get("currency") or item.get("isoCurrencyCode") or "GBP")
    return {
        "amount_gbp": round(amount, 2),
        "date": dated,
        "posted_on": dated,
        "account_name": account_name,
        "account_external_id": str(item.get("account_id") or item.get("accountId") or ""),
        "external_id": external_id or None,
        "description": description,
        "currency": currency,
        "scope": str(item.get("scope") or "personal"),
    }


class LunchFlowProvider(BaseFinanceProvider):
    name = "lunchflow"

    def __init__(self, config: LunchFlowConfig) -> None:
        self._client = LunchFlowClient(config)
        self._business_connection_ids = parse_business_connection_ids(
            config.business_connection_ids
        )

    def _ensure_configured(self) -> None:
        if not self._client.configured:
            raise IntegrationNotConfiguredError(
                "Lunch Flow is not configured. Paste your API key in Settings."
            )

    async def sync_accounts(self) -> list[dict[str, Any]]:
        self._ensure_configured()
        try:
            accounts = await self._client.fetch_accounts()
        except LunchFlowError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc

        normalized: list[dict[str, Any]] = []
        for record in accounts:
            account_id = str(record.get("id") or record.get("accountId") or "")
            if not account_id:
                continue
            current: float | None = None
            available: float | None = None
            fallback = 0.0
            try:
                detail = await self._client.fetch_balance_detail(account_id)
                current = detail.get("current")
                available = detail.get("available")
                fallback = float(detail.get("fallback") or 0.0)
            except LunchFlowError:
                raw_balance = record.get("balance")
                if isinstance(raw_balance, dict):
                    fallback = float(raw_balance.get("amount") or 0)
                    if raw_balance.get("available") is not None:
                        available = float(raw_balance["available"])
                else:
                    try:
                        fallback = float(raw_balance or 0)
                    except (TypeError, ValueError):
                        fallback = 0.0
            display_name = str(
                record.get("name")
                or record.get("displayName")
                or record.get("institutionName")
                or "Bank account"
            )
            provider_name = str(
                record.get("institution_name")
                or record.get("institutionName")
                or record.get("institution")
                or record.get("provider")
                or "Lunch Flow"
            )
            raw_type = str(record.get("type") or record.get("accountType") or "")
            mapped = _map_account_type(raw_type, display_name)
            if provider_name and provider_name.lower() not in display_name.lower():
                display_name = f"{provider_name} — {display_name}"
            credit_limit = _optional_amount(
                record.get("creditLimit") or record.get("credit_limit") or record.get("limit")
            )
            scope = infer_lunchflow_scope(
                record,
                display_name=display_name,
                provider_name=provider_name,
                business_connection_ids=self._business_connection_ids,
            )
            balance = credit_card_balance_gbp(
                account_type=mapped,
                credit_limit_gbp=credit_limit,
                current=current,
                available=available,
                fallback=fallback,
            )
            normalized.append(
                {
                    "scope": scope.value,
                    "account_type": mapped.value,
                    "name": display_name,
                    "provider": provider_name,
                    "balance_gbp": round(balance, 2),
                    "credit_limit_gbp": credit_limit,
                    "external_id": account_id,
                    "connection_id": str(record.get("connectionId") or record.get("connection_id") or ""),
                    "notes": "Synced via Lunch Flow Open Banking",
                }
            )
        return normalized

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        self._ensure_configured()
        try:
            accounts = await self._client.fetch_accounts()
        except LunchFlowError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
        cutoff = since or (datetime.now(timezone.utc) - timedelta(days=730)).date().isoformat()
        collected: list[dict[str, Any]] = []
        account_scopes: dict[str, str] = {}
        for record in accounts:
            account_id = str(record.get("id") or record.get("accountId") or "")
            if not account_id:
                continue
            provider_name = str(
                record.get("institution_name")
                or record.get("institutionName")
                or record.get("institution")
                or record.get("provider")
                or "Lunch Flow"
            )
            display_name = str(
                record.get("name") or record.get("displayName") or record.get("institutionName") or ""
            )
            account_scopes[account_id] = infer_lunchflow_scope(
                record,
                display_name=display_name,
                provider_name=provider_name,
                business_connection_ids=self._business_connection_ids,
            ).value
        for record in accounts:
            account_id = str(record.get("id") or record.get("accountId") or "")
            if not account_id:
                continue
            transactions = await self._client.fetch_transactions(account_id, since=cutoff)
            account_name = str(record.get("name") or record.get("displayName") or "")
            scope = account_scopes.get(account_id, FinanceScope.PERSONAL.value)
            for item in transactions:
                item = dict(item)
                item.setdefault("account_id", account_id)
                item["scope"] = scope
                normalized_tx = _normalize_transaction(item, cutoff, account_name=account_name)
                if normalized_tx:
                    collected.append(normalized_tx)
        return collected

    async def summarise_recent_activity(self) -> tuple[float, float]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
        transactions = await self.sync_transactions(since=cutoff)
        current = [
            item
            for item in transactions
            if "current" in str(item.get("account_name") or "").lower()
        ]
        chosen = current or transactions
        income = sum(item["amount_gbp"] for item in chosen if item["amount_gbp"] > 0)
        spending = sum(-item["amount_gbp"] for item in chosen if item["amount_gbp"] < 0)
        return round(income, 2), round(spending, 2)

    async def test_connection(self) -> dict[str, Any]:
        self._ensure_configured()
        try:
            accounts = await self._client.fetch_accounts()
        except LunchFlowError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
        return {"ok": True, "account_count": len(accounts)}
