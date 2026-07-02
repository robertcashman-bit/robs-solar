"""QuickFile API client — same auth model as Custody Note (MD5 per request)."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

import httpx

from app.schemas.finance import QuickFileConfig

logger = logging.getLogger(__name__)

QF_HOST = "api.quickfile.co.uk"
QF_BASE = f"https://{QF_HOST}"

# QuickFile bank/getaccounts requires both fields in SearchParameters.
_BANK_ACCOUNT_TYPES = [
    "CURRENT",
    "PETTY",
    "BUILDINGSOC",
    "LOAN",
    "MERCHANT",
    "EQUITY",
    "CREDITCARD",
    "RESERVE",
]


def _bank_accounts_search_parameters() -> dict[str, Any]:
    return {
        "OrderResultsBy": "Position",
        "AccountTypes": {"AccountType": _BANK_ACCOUNT_TYPES},
        "ShowHidden": False,
        "GetOpenBankingConsents": False,
    }


def _client_search_parameters(*, return_count: int, offset: int = 0) -> dict[str, Any]:
    return {
        "ReturnCount": return_count,
        "Offset": offset,
        "OrderResultsBy": "CompanyName",
        "OrderDirection": "ASC",
    }


def _invoice_search_parameters(
    *,
    return_count: int,
    offset: int = 0,
    status: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "ReturnCount": return_count,
        "Offset": offset,
        "OrderResultsBy": "InvoiceNumber",
        "OrderDirection": "DESC",
        "InvoiceType": "INVOICE",
    }
    if status:
        params["Status"] = status
    return params


class QuickFileError(Exception):
    """QuickFile API returned an error."""


def build_quickfile_auth(
    config: QuickFileConfig,
    *,
    submission_number: str | None = None,
) -> dict[str, str]:
    account_number = config.account_number.strip()
    api_key = config.api_key.strip()
    application_id = config.application_id.strip()
    missing = []
    if not account_number:
        missing.append("Account number")
    if not api_key:
        missing.append("API key")
    if not application_id:
        missing.append("Application ID")
    if missing:
        raise QuickFileError(
            "QuickFile not configured — missing: " + ", ".join(missing) + "."
        )
    sub = submission_number or f"rf-{uuid.uuid4().hex[:12]}"
    md5_value = hashlib.md5(
        f"{account_number}{api_key}{sub}".encode()
    ).hexdigest().lower()
    return {
        "account_number": account_number,
        "submission_number": sub,
        "md5_value": md5_value,
        "application_id": application_id,
    }


def parse_quickfile_response(status_code: int, raw: str) -> dict[str, Any]:
    text = raw or ""
    if not text.strip():
        raise QuickFileError(f"QuickFile returned empty response (HTTP {status_code})")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise QuickFileError(
            f"QuickFile response parse error (HTTP {status_code})"
        ) from exc

    errors = payload.get("Errors")
    if errors:
        err_items = errors.get("Error") if isinstance(errors, dict) else errors
        if not isinstance(err_items, list):
            err_items = [err_items]
        messages = []
        for item in err_items:
            if isinstance(item, dict):
                messages.append(
                    str(item.get("Message") or item.get("Detail") or item)
                )
            else:
                messages.append(str(item))
        raise QuickFileError("; ".join(messages))

    if status_code < 200 or status_code >= 300:
        raise QuickFileError(f"QuickFile HTTP {status_code}: {text[:300]}")

    root_key = next(
        (
            key
            for key in payload
            if isinstance(payload[key], dict) and "Header" in payload[key]
        ),
        None,
    )
    message = (
        payload[root_key]
        if root_key
        else payload.get("payload", {}).get("Message") or payload.get("Message") or payload
    )
    header = message.get("Header") if isinstance(message, dict) else None
    if isinstance(header, dict) and header.get("Status") == "Error":
        err_msg = (
            header.get("StatusMessage")
            or header.get("ErrorMessage")
            or (message.get("Body") or {}).get("ErrorMessage")
            or "Unknown QuickFile error"
        )
        raise QuickFileError(str(err_msg))
    body = message.get("Body") if isinstance(message, dict) else {}
    return body if isinstance(body, dict) else {}


def _extract_records(body: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("Record", "Records", "BankAccountDetails", "BankAccounts", "Account"):
        value = body.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
    return []


class QuickFileClient:
    def __init__(self, config: QuickFileConfig) -> None:
        self._config = config

    async def request(self, api_path: str, body_content: dict[str, Any]) -> dict[str, Any]:
        auth = build_quickfile_auth(self._config)
        post_data = {
            "payload": {
                "Header": {
                    "MessageType": "Request",
                    "SubmissionNumber": auth["submission_number"],
                    "Authentication": {
                        "AccNumber": auth["account_number"],
                        "MD5Value": auth["md5_value"],
                        "ApplicationID": auth["application_id"],
                    },
                },
                "Body": body_content,
            }
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{QF_BASE}{api_path}",
                json=post_data,
                headers={"Content-Type": "application/json"},
            )
        return parse_quickfile_response(response.status_code, response.text)

    async def test_connection(self) -> dict[str, Any]:
        body = await self.request(
            "/1_2/client/search",
            {"SearchParameters": _client_search_parameters(return_count=1)},
        )
        records = _extract_records(body)
        return {"ok": True, "sample_count": len(records)}

    async def fetch_bank_accounts(self) -> list[dict[str, Any]]:
        body = await self.request(
            "/1_2/bank/getaccounts",
            {"SearchParameters": _bank_accounts_search_parameters()},
        )
        accounts = _extract_records(body)
        if not accounts and isinstance(body.get("BankAccounts"), dict):
            grouped = body["BankAccounts"]
            for value in grouped.values():
                if isinstance(value, list):
                    accounts.extend(item for item in value if isinstance(item, dict))
                elif isinstance(value, dict):
                    accounts.append(value)
        return accounts

    async def fetch_bank_balances(
        self, nominal_codes: list[str]
    ) -> dict[str, float]:
        if not nominal_codes:
            return {}
        body = await self.request(
            "/1_2/bank/getaccountbalances",
            {"NominalCodes": {"NominalCode": nominal_codes}},
        )
        balances: dict[str, float] = {}
        for record in _extract_records(body):
            code = str(
                record.get("NominalCode")
                or record.get("Nominal")
                or record.get("Code")
                or ""
            ).strip()
            if not code:
                continue
            amount = (
                record.get("Balance")
                or record.get("AccountBalance")
                or record.get("ClosingBalance")
                or 0
            )
            try:
                balances[code] = float(amount)
            except (TypeError, ValueError):
                balances[code] = 0.0
        return balances

    async def fetch_unpaid_invoice_total(self) -> float:
        body = await self.request(
            "/1_2/invoice/search",
            {
                "SearchParameters": _invoice_search_parameters(
                    return_count=200,
                    status="UNPAID",
                )
            },
        )
        total = 0.0
        for record in _extract_records(body):
            due = (
                record.get("AmountDue")
                or record.get("OutstandingAmount")
                or record.get("GrossTotal")
                or record.get("TotalAmount")
                or 0
            )
            try:
                total += float(due)
            except (TypeError, ValueError):
                continue
        return round(total, 2)
