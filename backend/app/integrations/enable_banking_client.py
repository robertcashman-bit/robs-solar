"""Enable Banking Open Banking HTTP client."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt

from app.integrations.gocardless_client import map_cash_account_type
from app.schemas.finance import OpenBankingConfig

logger = logging.getLogger(__name__)

ENABLE_BASE = "https://api.enablebanking.com"
JWT_ISS = "enablebanking.com"
JWT_AUD = "api.enablebanking.com"


class EnableBankingError(Exception):
    """Raised when Enable Banking returns an error response."""


def _pick_enable_balance(balances: list[dict[str, Any]]) -> float | None:
    preferred = ("CLAV", "ITAV", "OPAV", "OTHR", "BOOK")
    by_type = {
        str(item.get("balance_type") or ""): item for item in balances if isinstance(item, dict)
    }
    for balance_type in preferred:
        record = by_type.get(balance_type)
        if not record:
            continue
        amount_obj = record.get("balance_amount") or {}
        amount = amount_obj.get("amount")
        if amount is None or amount == "":
            continue
        try:
            return float(amount)
        except (TypeError, ValueError):
            continue
    for record in balances:
        amount_obj = record.get("balance_amount") or {}
        amount = amount_obj.get("amount")
        if amount is None or amount == "":
            continue
        try:
            return float(amount)
        except (TypeError, ValueError):
            continue
    return None


def parse_institution_id(institution_id: str) -> tuple[str, str]:
    if ":" in institution_id:
        country, name = institution_id.split(":", 1)
        return country.upper(), name
    return "GB", institution_id


def encode_institution_id(country: str, name: str) -> str:
    return f"{country.upper()}:{name}"


class EnableBankingClient:
    def __init__(self, config: OpenBankingConfig) -> None:
        self._config = config

    def _build_jwt(self) -> str:
        if not self._config.application_id or not self._config.private_key_pem:
            raise EnableBankingError("Enable Banking requires application_id and private_key_pem")
        now = datetime.now(timezone.utc)
        payload = {
            "iss": JWT_ISS,
            "aud": JWT_AUD,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        }
        headers = {
            "typ": "JWT",
            "alg": "RS256",
            "kid": self._config.application_id,
        }
        return jwt.encode(
            payload,
            self._config.private_key_pem,
            algorithm="RS256",
            headers=headers,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = self._build_jwt()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"
        url = f"{ENABLE_BASE}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, headers=headers, json=json, params=params)
        if response.status_code >= 400:
            detail = response.text[:500]
            raise EnableBankingError(f"Enable Banking {response.status_code}: {detail}")
        data = response.json()
        if not isinstance(data, dict):
            raise EnableBankingError("Unexpected Enable Banking response shape")
        return data

    async def test_connection(self) -> dict[str, object]:
        body = await self._request("GET", "/application")
        return {"ok": True, "application_name": str(body.get("name") or "")}

    async def list_aspsps(self, *, country: str = "GB", query: str = "") -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if country:
            params["country"] = country.upper()
        body = await self._request("GET", "/aspsps", params=params)
        aspsps = body.get("aspsps")
        if not isinstance(aspsps, list):
            raise EnableBankingError("Unexpected ASPSPs response")
        needle = query.strip().lower()
        results: list[dict[str, Any]] = []
        for item in aspsps:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            country_code = str(item.get("country") or country).upper()
            if not name:
                continue
            if needle and needle not in name.lower():
                continue
            results.append(
                {
                    "id": encode_institution_id(country_code, name),
                    "name": name,
                    "logo": str(item.get("logo") or ""),
                    "country": country_code,
                }
            )
        results.sort(key=lambda row: row["name"].lower())
        return results[:40]

    async def start_auth(
        self,
        *,
        country: str,
        aspsp_name: str,
        redirect_url: str,
        state: str,
    ) -> dict[str, Any]:
        valid_until = (datetime.now(timezone.utc) + timedelta(days=90)).strftime(
            "%Y-%m-%dT%H:%M:%S.000000+00:00"
        )
        body = await self._request(
            "POST",
            "/auth",
            json={
                "access": {"valid_until": valid_until, "balances": True, "details": True},
                "aspsp": {"name": aspsp_name, "country": country.upper()},
                "state": state,
                "redirect_url": redirect_url,
                "psu_type": "personal",
            },
        )
        return body

    async def authorize_session(self, *, code: str) -> dict[str, Any]:
        return await self._request("POST", "/sessions", json={"code": code})

    async def get_session(self, session_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/sessions/{session_id}")

    async def get_account_balances(self, account_uid: str) -> dict[str, Any]:
        return await self._request("GET", f"/accounts/{account_uid}/balances")

    async def get_account_transactions(
        self,
        account_uid: str,
        date_from: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if date_from:
            query["date_from"] = date_from
        else:
            query["date_from"] = (
                (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()
            )

        all_transactions: list[dict[str, Any]] = []
        continuation_key: str | None = None
        while True:
            params = dict(query)
            if continuation_key:
                params["continuation_key"] = continuation_key
            body = await self._request(
                "GET",
                f"/accounts/{account_uid}/transactions",
                params=params,
            )
            transactions = body.get("transactions")
            if isinstance(transactions, list):
                all_transactions.extend(item for item in transactions if isinstance(item, dict))
            continuation_key = body.get("continuation_key")
            if not continuation_key:
                break
        return all_transactions

    async def fetch_account_record(
        self,
        *,
        account: dict[str, Any],
        institution_name: str,
    ) -> dict[str, Any] | None:
        uid = str(account.get("uid") or "")
        if not uid:
            return None
        name = str(account.get("name") or account.get("product") or institution_name).strip()
        cash_type = str(account.get("cash_account_type") or "")
        account_type = map_cash_account_type(cash_type, name)
        try:
            balances_body = await self.get_account_balances(uid)
        except EnableBankingError as exc:
            logger.warning("Enable Banking balance fetch failed for %s: %s", uid, exc)
            return None
        balances = balances_body.get("balances")
        balance_list = balances if isinstance(balances, list) else []
        amount = _pick_enable_balance(balance_list)
        if amount is None:
            amount = 0.0
        if account_type in ("credit_card", "loan", "mortgage"):
            amount = abs(amount)
        return {
            "scope": "personal",
            "account_type": account_type,
            "name": name,
            "provider": institution_name,
            "balance_gbp": round(amount, 2),
            "external_id": f"openbanking:enable:{uid}",
            "notes": f"Synced via Enable Banking ({institution_name})",
        }
