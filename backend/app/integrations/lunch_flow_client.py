"""Lunch Flow REST API client — personal bank accounts via API key."""

from __future__ import annotations

from typing import Any

import httpx

from app.schemas.finance import LunchFlowConfig

# Must be the www host: the apex domain 308-redirects and would break API calls.
LUNCH_FLOW_BASE = "https://www.lunchflow.app/api/v1"


class LunchFlowError(Exception):
    pass


class LunchFlowClient:
    def __init__(self, config: LunchFlowConfig) -> None:
        self._api_key = config.api_key.strip()

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "Accept": "application/json",
        }

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(
                f"{LUNCH_FLOW_BASE}{path}", headers=self._headers(), params=params
            )
        if response.status_code == 401:
            raise LunchFlowError("Invalid Lunch Flow API key")
        if response.status_code == 403:
            # 403 covers both invalid credentials and missing subscription — surface
            # the API's own message rather than guessing.
            message = ""
            try:
                body = response.json()
                message = str(body.get("message") or "")
            except Exception:
                message = ""
            raise LunchFlowError(
                f"Lunch Flow rejected the API key: {message}"
                if message
                else "Lunch Flow rejected the API key. Check it at lunchflow.app"
            )
        if response.status_code >= 400:
            try:
                body = response.json()
                message = body.get("message") or body.get("error") or response.text
            except Exception:
                message = response.text
            raise LunchFlowError(f"Lunch Flow {response.status_code}: {message}")
        return response.json()

    async def test_connection(self) -> dict[str, object]:
        body = await self._get("/accounts")
        accounts = body.get("accounts") if isinstance(body, dict) else []
        count = len(accounts) if isinstance(accounts, list) else 0
        result: dict[str, object] = {"accounts": count}
        if count == 0:
            result["hint"] = (
                "Lunch Flow returned 0 accounts. Open Destinations → your API destination "
                "→ Account Access and enable the bank account."
            )
        return result

    async def list_accounts(self) -> list[dict[str, Any]]:
        body = await self._get("/accounts")
        accounts = body.get("accounts") if isinstance(body, dict) else []
        return [row for row in accounts if isinstance(row, dict)]

    async def get_account_balance(self, account_id: int) -> dict[str, Any]:
        body = await self._get(f"/accounts/{account_id}/balance")
        balance = body.get("balance") if isinstance(body, dict) else {}
        return balance if isinstance(balance, dict) else {}

    async def get_account_transactions(
        self,
        account_id: int,
        *,
        date_from: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"include_pending": "true"}
        if date_from:
            params["from"] = date_from
        body = await self._get(f"/accounts/{account_id}/transactions", params=params)
        transactions = body.get("transactions") if isinstance(body, dict) else []
        return [row for row in transactions if isinstance(row, dict)]
