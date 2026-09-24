"""Lunch Flow personal API client (Open Banking via existing Lunchflow connections)."""

from __future__ import annotations

from typing import Any

import httpx

from app.schemas.finance import LunchFlowConfig

# Lunch Flow redirects the apex host to www; call www directly.
LUNCHFLOW_BASE = "https://www.lunchflow.app/api/v1"


class LunchFlowError(Exception):
    pass


class LunchFlowClient:
    def __init__(self, config: LunchFlowConfig) -> None:
        self._config = config

    @property
    def configured(self) -> bool:
        return bool(self._config.api_key.strip())

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._config.api_key.strip(),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "RobsFinance/1.0",
        }

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        if not self.configured:
            raise LunchFlowError("Lunch Flow is not configured. Paste the API key in Settings.")
        async with httpx.AsyncClient(
            base_url=LUNCHFLOW_BASE,
            timeout=45.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(path, headers=self._headers(), params=params)
        if response.status_code in (401, 403):
            raise LunchFlowError("Lunch Flow rejected the API key.")
        if response.status_code >= 400:
            raise LunchFlowError(f"Lunch Flow API error ({response.status_code}).")
        data = response.json()
        return data if isinstance(data, dict) else {"data": data}

    async def fetch_accounts(self) -> list[dict[str, Any]]:
        body = await self._get("/accounts")
        accounts = body.get("accounts")
        if isinstance(accounts, list):
            return accounts
        if isinstance(body.get("data"), list):
            return body["data"]
        return []

    async def fetch_balance_detail(self, account_id: str) -> dict[str, float | None]:
        body = await self._get(f"/accounts/{account_id}/balance")
        current: float | None = None
        available: float | None = None
        balance = body.get("balance")
        if isinstance(balance, dict):
            if balance.get("amount") is not None:
                current = float(balance["amount"])
            if balance.get("available") is not None:
                available = float(balance["available"])
            if balance.get("current") is not None and current is None:
                current = float(balance["current"])
        if body.get("amount") is not None:
            current = float(body["amount"])
        if body.get("current") is not None:
            current = float(body["current"])
        if body.get("available") is not None:
            available = float(body["available"])
        fallback = current if current is not None else (available if available is not None else 0.0)
        return {"current": current, "available": available, "fallback": fallback}

    async def fetch_balance(self, account_id: str) -> float:
        detail = await self.fetch_balance_detail(account_id)
        return float(detail.get("fallback") or 0.0)

    async def fetch_transactions(
        self, account_id: str, *, since: str | None = None
    ) -> list[dict[str, Any]]:
        params = {"start_date": since} if since else None
        body = await self._get(f"/accounts/{account_id}/transactions", params=params)
        transactions = body.get("transactions")
        if isinstance(transactions, list):
            return transactions
        data = body.get("data")
        if isinstance(data, list):
            return data
        return []
