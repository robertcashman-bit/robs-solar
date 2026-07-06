"""GoCardless Bank Account Data (Open Banking) HTTP client."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.schemas.finance import OpenBankingConfig

logger = logging.getLogger(__name__)

GOCARDLESS_BASE = "https://bankaccountdata.gocardless.com/api/v2"


class GoCardlessError(Exception):
    """Raised when GoCardless returns an error response."""


def _pick_balance_amount(balances: list[dict[str, Any]]) -> float | None:
    preferred = ("interimAvailable", "closingBooked", "expected")
    by_type = {
        str(item.get("balanceType") or ""): item for item in balances if isinstance(item, dict)
    }
    for balance_type in preferred:
        record = by_type.get(balance_type)
        if not record:
            continue
        amount = (record.get("balanceAmount") or {}).get("amount")
        if amount is None or amount == "":
            continue
        try:
            return float(amount)
        except (TypeError, ValueError):
            continue
    for record in balances:
        amount = (record.get("balanceAmount") or {}).get("amount")
        if amount is None or amount == "":
            continue
        try:
            return float(amount)
        except (TypeError, ValueError):
            continue
    return None


def map_cash_account_type(raw: str | None, name: str) -> str:
    value = (raw or "").upper()
    label = (name or "").lower()
    if value == "CARD" or "credit card" in label or "credit" in label:
        return "credit_card"
    if value == "LOAN" or "loan" in label:
        return "loan"
    if value == "MORT" or "mortgage" in label:
        return "mortgage"
    if value == "SVGS" or "savings" in label:
        return "other"
    return "current"


class GoCardlessClient:
    def __init__(self, config: OpenBankingConfig) -> None:
        self._config = config
        self._access_token = config.access_token
        self._refresh_token = config.refresh_token
        self._access_expires_at = config.access_expires_at

    async def _ensure_access_token(self) -> str:
        now = datetime.now(timezone.utc)
        if (
            self._access_token
            and self._access_expires_at
            and self._access_expires_at > now + timedelta(minutes=2)
        ):
            return self._access_token

        if self._refresh_token:
            body = await self._request(
                "POST",
                "/token/refresh/",
                json={"refresh": self._refresh_token},
                auth=False,
            )
        else:
            body = await self._request(
                "POST",
                "/token/new/",
                json={
                    "secret_id": self._config.secret_id,
                    "secret_key": self._config.secret_key,
                },
                auth=False,
            )
            self._refresh_token = str(body.get("refresh") or self._refresh_token or "")

        access = str(body.get("access") or "")
        if not access:
            raise GoCardlessError("GoCardless did not return an access token")
        self._access_token = access
        expires_in = int(body.get("access_expires") or 86400)
        self._access_expires_at = now + timedelta(seconds=max(60, expires_in - 120))
        return access

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        headers = {"accept": "application/json"}
        if auth:
            token = await self._ensure_access_token()
            headers["Authorization"] = f"Bearer {token}"
        url = f"{GOCARDLESS_BASE}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, headers=headers, json=json, params=params)
        if response.status_code >= 400:
            detail = response.text[:500]
            raise GoCardlessError(f"GoCardless {response.status_code}: {detail}")
        data = response.json()
        if not isinstance(data, dict):
            raise GoCardlessError("Unexpected GoCardless response shape")
        return data

    def export_tokens(self) -> dict[str, str | None]:
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "access_expires_at": (
                self._access_expires_at.isoformat() if self._access_expires_at else None
            ),
        }

    async def test_connection(self) -> dict[str, object]:
        institutions = await self.list_institutions(country="gb")
        return {"ok": True, "institution_count": len(institutions)}

    async def list_institutions(self, *, country: str = "gb") -> list[dict[str, Any]]:
        data = await self._get_json("/institutions/", params={"country": country.upper()})
        if not isinstance(data, list):
            raise GoCardlessError("Unexpected institutions response")
        return [item for item in data if isinstance(item, dict)]

    async def _get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> Any:
        headers = {"accept": "application/json"}
        if auth:
            token = await self._ensure_access_token()
            headers["Authorization"] = f"Bearer {token}"
        url = f"{GOCARDLESS_BASE}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
        if response.status_code >= 400:
            raise GoCardlessError(f"GoCardless {response.status_code}: {response.text[:500]}")
        return response.json()

    async def create_end_user_agreement(self, institution_id: str) -> str:
        body = await self._request(
            "POST",
            "/agreements/enduser/",
            json={
                "institution_id": institution_id,
                "max_historical_days": 90,
                "access_valid_for_days": 90,
                "access_scope": ["balances", "details"],
            },
        )
        agreement_id = str(body.get("id") or "")
        if not agreement_id:
            raise GoCardlessError("GoCardless did not return an agreement id")
        return agreement_id

    async def create_requisition(
        self,
        *,
        institution_id: str,
        redirect_url: str,
        reference: str,
    ) -> dict[str, Any]:
        agreement_id = await self.create_end_user_agreement(institution_id)
        body = await self._request(
            "POST",
            "/requisitions/",
            json={
                "redirect": redirect_url,
                "institution_id": institution_id,
                "reference": reference,
                "agreement": agreement_id,
                "user_language": "EN",
            },
        )
        return body

    async def get_requisition(self, requisition_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/requisitions/{requisition_id}/")

    async def get_account_details(self, account_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/accounts/{account_id}/details/")

    async def get_account_balances(self, account_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/accounts/{account_id}/balances/")

    async def fetch_account_record(
        self,
        *,
        account_id: str,
        institution_name: str,
    ) -> dict[str, Any] | None:
        try:
            details_body = await self.get_account_details(account_id)
            balances_body = await self.get_account_balances(account_id)
        except GoCardlessError as exc:
            logger.warning("GoCardless account fetch failed for %s: %s", account_id, exc)
            return None

        account = (
            details_body.get("account")
            if isinstance(details_body.get("account"), dict)
            else {}
        )
        name = str(account.get("name") or account.get("product") or institution_name).strip()
        cash_type = str(account.get("cashAccountType") or "")
        account_type = map_cash_account_type(cash_type, name)
        balances = balances_body.get("balances")
        balance_list = balances if isinstance(balances, list) else []
        amount = _pick_balance_amount(balance_list)
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
            "external_id": f"openbanking:gocardless:{account_id}",
            "notes": f"Synced via GoCardless Open Banking ({institution_name})",
        }
