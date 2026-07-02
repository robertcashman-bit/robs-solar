"""QuickFile finance provider — bank accounts and unpaid invoice totals."""

from __future__ import annotations

from typing import Any

from app.integrations.base import BaseFinanceProvider, IntegrationNotConfiguredError
from app.integrations.quickfile_client import QuickFileClient, QuickFileError
from app.schemas.finance import FinanceAccountType, FinanceScope, QuickFileConfig


def _map_account_type(raw: str, name: str) -> FinanceAccountType:
    value = (raw or "").upper()
    label = (name or "").lower()
    if value == "CREDITCARD" or "credit card" in label:
        return FinanceAccountType.CREDIT_CARD
    if value == "LOAN" or "loan" in label:
        return FinanceAccountType.LOAN
    if "vat" in label:
        return FinanceAccountType.VAT_RESERVE
    if "corp" in label or "corporation tax" in label:
        return FinanceAccountType.CORP_TAX_RESERVE
    if "capital on tap" in label:
        return FinanceAccountType.CAPITAL_ON_TAP
    return FinanceAccountType.CURRENT


def _nominal_code(record: dict[str, Any]) -> str:
    return str(
        record.get("NominalCode")
        or record.get("Nominal")
        or record.get("AccountID")
        or record.get("Id")
        or ""
    ).strip()


def _account_name(record: dict[str, Any]) -> str:
    return str(
        record.get("AccountName")
        or record.get("Name")
        or record.get("BankName")
        or record.get("Description")
        or "QuickFile account"
    ).strip()


class QuickFileProvider(BaseFinanceProvider):
    name = "quickfile"

    def __init__(self, config: QuickFileConfig) -> None:
        self._config = config
        self._client = QuickFileClient(config)

    def _ensure_configured(self) -> None:
        if not (
            self._config.account_number
            and self._config.api_key
            and self._config.application_id
        ):
            raise IntegrationNotConfiguredError(
                "QuickFile is not configured. Set QUICKFILE_* env vars or save "
                "credentials under Settings → Finance."
            )

    async def sync_accounts(self) -> list[dict[str, Any]]:
        self._ensure_configured()
        try:
            accounts = await self._client.fetch_bank_accounts()
            codes = [_nominal_code(item) for item in accounts if _nominal_code(item)]
            balances = await self._client.fetch_bank_balances(codes)
        except QuickFileError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc

        normalized: list[dict[str, Any]] = []
        for record in accounts:
            code = _nominal_code(record)
            if not code:
                continue
            account_type = record.get("AccountType") or record.get("Type") or "CURRENT"
            name = _account_name(record)
            balance = balances.get(code)
            if balance is None:
                try:
                    balance = float(
                        record.get("Balance")
                        or record.get("AccountBalance")
                        or 0
                    )
                except (TypeError, ValueError):
                    balance = 0.0
            mapped = _map_account_type(str(account_type), name)
            normalized.append(
                {
                    "scope": FinanceScope.BUSINESS.value,
                    "account_type": mapped.value,
                    "name": name,
                    "provider": "QuickFile",
                    "balance_gbp": round(float(balance), 2),
                    "external_id": code,
                    "notes": f"QuickFile nominal {code}",
                }
            )
        return normalized

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        self._ensure_configured()
        return []

    async def fetch_debtors_gbp(self) -> float:
        self._ensure_configured()
        try:
            return await self._client.fetch_unpaid_invoice_total()
        except QuickFileError:
            return 0.0

    async def test_connection(self) -> dict[str, Any]:
        self._ensure_configured()
        try:
            return await self._client.test_connection()
        except QuickFileError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
