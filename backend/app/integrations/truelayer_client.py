"""TrueLayer Open Banking client (UK)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

from app.schemas.finance import TrueLayerConfig


class TrueLayerError(Exception):
    pass


class TrueLayerClient:
    def __init__(self, config: TrueLayerConfig, *, access_token: str = "") -> None:
        self._config = config
        self._access_token = access_token

    def _auth_base(self) -> str:
        return (
            "https://auth.truelayer.com"
            if self._config.environment.lower() == "live"
            else "https://auth.truelayer-sandbox.com"
        )

    def _api_base(self) -> str:
        return (
            "https://api.truelayer.com"
            if self._config.environment.lower() == "live"
            else "https://api.truelayer-sandbox.com"
        )

    @property
    def configured(self) -> bool:
        return bool(
            self._config.client_id
            and self._config.client_secret
            and self._config.redirect_uri
        )

    def build_authorize_url(self, *, state: str) -> str:
        if not self.configured:
            raise TrueLayerError("TrueLayer is not configured")
        scopes = "info accounts balance transactions cards offline_access"
        redirect = quote(self._config.redirect_uri, safe="")
        return (
            f"{self._auth_base()}/?response_type=code"
            f"&client_id={quote(self._config.client_id, safe='')}"
            f"&redirect_uri={redirect}"
            f"&scope={quote(scopes, safe='')}"
            f"&state={quote(state, safe='')}"
        )

    async def exchange_code(self, code: str) -> dict[str, Any]:
        if not self.configured:
            raise TrueLayerError("TrueLayer is not configured")
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self._auth_base()}/connect/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                    "redirect_uri": self._config.redirect_uri,
                    "code": code,
                },
            )
        if response.status_code >= 400:
            raise TrueLayerError(f"Token exchange failed: {response.text}")
        return response.json()

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self._auth_base()}/connect/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                    "refresh_token": refresh_token,
                },
            )
        if response.status_code >= 400:
            raise TrueLayerError(f"Token refresh failed: {response.text}")
        return response.json()

    async def fetch_accounts(self) -> list[dict[str, Any]]:
        if not self._access_token:
            raise TrueLayerError("TrueLayer access token missing")
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self._api_base()}/data/v1/accounts",
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        if response.status_code >= 400:
            raise TrueLayerError(f"Accounts fetch failed: {response.text}")
        return response.json().get("results", [])

    async def fetch_balance(self, account_id: str) -> float:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self._api_base()}/data/v1/accounts/{account_id}/balance",
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        if response.status_code >= 400:
            raise TrueLayerError(f"Balance fetch failed: {response.text}")
        results = response.json().get("results", [])
        if not results:
            return 0.0
        current = results[0].get("current", 0)
        try:
            return float(current)
        except (TypeError, ValueError):
            return 0.0

    async def fetch_transactions(
        self,
        account_id: str,
        *,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        if not self._access_token:
            raise TrueLayerError("TrueLayer access token missing")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._api_base()}/data/v1/accounts/{account_id}/transactions",
                params={"from": from_date, "to": to_date},
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        if response.status_code >= 400:
            raise TrueLayerError(f"Transactions fetch failed: {response.text}")
        results = response.json().get("results", [])
        return results if isinstance(results, list) else []

    async def fetch_cards(self) -> list[dict[str, Any]]:
        if not self._access_token:
            raise TrueLayerError("TrueLayer access token missing")
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self._api_base()}/data/v1/cards",
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        if response.status_code >= 400:
            raise TrueLayerError(f"Cards fetch failed: {response.text}")
        results = response.json().get("results", [])
        return results if isinstance(results, list) else []

    async def fetch_card_balance(self, card_id: str) -> dict[str, float | None]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self._api_base()}/data/v1/cards/{card_id}/balance",
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        if response.status_code >= 400:
            raise TrueLayerError(f"Card balance fetch failed: {response.text}")
        results = response.json().get("results", [])
        if not results:
            return {"current": 0.0, "credit_limit": None}
        row = results[0]
        try:
            current = float(row.get("current") or 0)
        except (TypeError, ValueError):
            current = 0.0
        try:
            limit_raw = row.get("credit_limit")
            credit_limit = float(limit_raw) if limit_raw is not None else None
        except (TypeError, ValueError):
            credit_limit = None
        return {"current": current, "credit_limit": credit_limit}

    async def fetch_card_transactions(
        self,
        card_id: str,
        *,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        if not self._access_token:
            raise TrueLayerError("TrueLayer access token missing")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._api_base()}/data/v1/cards/{card_id}/transactions",
                params={"from": from_date, "to": to_date},
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        if response.status_code >= 400:
            raise TrueLayerError(f"Card transactions fetch failed: {response.text}")
        results = response.json().get("results", [])
        return results if isinstance(results, list) else []

    async def fetch_recent_transactions(self, *, days: int = 90) -> list[dict[str, Any]]:
        """Pull recent account and card transactions after a bank login."""
        today = datetime.now(timezone.utc).date()
        from_date = (today - timedelta(days=days)).isoformat()
        to_date = today.isoformat()
        collected: list[dict[str, Any]] = []
        try:
            accounts = await self.fetch_accounts()
        except TrueLayerError:
            accounts = []
        for record in accounts:
            account_id = str(record.get("account_id") or record.get("accountId") or "")
            if not account_id:
                continue
            try:
                rows = await self.fetch_transactions(
                    account_id, from_date=from_date, to_date=to_date
                )
            except TrueLayerError:
                continue
            account_name = str(record.get("display_name") or record.get("displayName") or "")
            for item in rows:
                item = dict(item)
                item.setdefault("account_id", account_id)
                item.setdefault("account_name", account_name)
                collected.append(item)
        try:
            cards = await self.fetch_cards()
        except TrueLayerError:
            cards = []
        for record in cards:
            card_id = str(record.get("account_id") or record.get("card_id") or "")
            if not card_id:
                continue
            try:
                rows = await self.fetch_card_transactions(
                    card_id, from_date=from_date, to_date=to_date
                )
            except TrueLayerError:
                continue
            card_name = str(record.get("display_name") or record.get("name_on_card") or "")
            for item in rows:
                item = dict(item)
                item.setdefault("account_id", card_id)
                item.setdefault("account_name", card_name)
                collected.append(item)
        return collected
