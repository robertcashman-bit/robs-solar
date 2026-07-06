"""QuickFile finance provider — bank accounts and unpaid invoice totals."""

from __future__ import annotations

from typing import Any

from app.integrations.base import BaseFinanceProvider, IntegrationNotConfiguredError
from datetime import datetime, timezone

from app.integrations.quickfile_client import QuickFileClient, QuickFileError, _nominal_code_key
from app.integrations.quickfile_reports import parse_balance_sheet_full
from app.schemas.finance import FinanceAccountType, FinanceScope, QuickFileConfig


def _map_account_type(raw: str, name: str) -> FinanceAccountType:
    value = (raw or "").upper()
    label = (name or "").lower()
    if value == "CREDITCARD" or "credit card" in label:
        return FinanceAccountType.CREDIT_CARD
    if "director" in label and "loan" in label:
        return FinanceAccountType.DIRECTORS_LOAN
    if value == "LOAN" or "loan" in label:
        return FinanceAccountType.LOAN
    if value == "RESERVE" or "vat" in label:
        return FinanceAccountType.VAT_RESERVE
    if "corp" in label or "corporation tax" in label:
        return FinanceAccountType.CORP_TAX_RESERVE
    if "capital on tap" in label:
        return FinanceAccountType.CAPITAL_ON_TAP
    return FinanceAccountType.CURRENT


def _nominal_code(record: dict[str, Any]) -> str:
    return _nominal_code_key(
        record.get("NominalCode")
        or record.get("Nominal")
        or record.get("AccountID")
        or record.get("Id")
    )


def _account_name(record: dict[str, Any]) -> str:
    return str(
        record.get("Name")
        or record.get("AccountName")
        or record.get("BankName")
        or record.get("Description")
        or "QuickFile account"
    ).strip()


def _normalize_balance(account_type: FinanceAccountType, amount: float) -> float:
    if account_type in (
        FinanceAccountType.CREDIT_CARD,
        FinanceAccountType.LOAN,
        FinanceAccountType.CAPITAL_ON_TAP,
        FinanceAccountType.DIRECTORS_LOAN,
        FinanceAccountType.CREDITORS,
    ):
        return round(abs(amount), 2)
    return round(amount, 2)


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
            account_type = (
                record.get("BankType")
                or record.get("AccountType")
                or record.get("Type")
                or "CURRENT"
            )
            name = _account_name(record)
            balance = balances.get(code)
            if balance is None:
                parsed = record.get("Balance") or record.get("AccountBalance")
                try:
                    balance = float(parsed) if parsed is not None else 0.0
                except (TypeError, ValueError):
                    balance = 0.0
            mapped = _map_account_type(str(account_type), name)
            normalized.append(
                {
                    "scope": FinanceScope.BUSINESS.value,
                    "account_type": mapped.value,
                    "name": name,
                    "provider": "QuickFile",
                    "balance_gbp": _normalize_balance(mapped, float(balance)),
                    "external_id": code,
                    "notes": f"QuickFile nominal {code}",
                }
            )
        return normalized

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        self._ensure_configured()
        return []

    async def fetch_debtors_gbp(self) -> float:
        """Debtors control balance from the balance sheet report (matches QuickFile BS)."""
        self._ensure_configured()
        try:
            to_date = datetime.now(timezone.utc).date().isoformat()
            body = await self._client.fetch_balance_sheet(to_date=to_date)
            parsed = parse_balance_sheet_full(body, to_date=to_date)
            return float(parsed["debtors_gbp"])
        except QuickFileError:
            return 0.0

    async def test_connection(self) -> dict[str, Any]:
        self._ensure_configured()
        try:
            return await self._client.test_connection()
        except QuickFileError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
