"""QuickFile finance provider — bank accounts, statement lines, invoices, purchases."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.integrations.base import BaseFinanceProvider, IntegrationNotConfiguredError
from app.integrations.quickfile_client import QuickFileClient, QuickFileError, _nominal_code_key
from app.integrations.quickfile_reports import parse_balance_sheet_full
from app.schemas.finance import FinanceAccountType, FinanceScope, QuickFileConfig
from app.services.finance.sync_lookback import (
    QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS,
    lookback_date_chunks,
)


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


def _parse_amount(record: dict[str, Any], *fields: str) -> float | None:
    for field in fields:
        raw = record.get(field)
        if raw is None or raw == "":
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def _parse_date(record: dict[str, Any], *fields: str) -> str:
    for field in fields:
        raw = record.get(field)
        if raw is None or raw == "":
            continue
        text = str(raw).strip()
        if len(text) >= 10:
            return text[:10]
    return ""


def _normalize_bank_line(
    record: dict[str, Any],
    *,
    nominal_code: str,
    account_name: str,
    cutoff: str,
) -> dict[str, Any] | None:
    dated = _parse_date(record, "TransactionDate", "Date", "PostedDate")
    if dated and cutoff and dated < cutoff:
        return None
    amount = _parse_amount(record, "Amount", "TransactionAmount")
    if amount is None or amount == 0:
        return None
    reference = str(record.get("Reference") or record.get("Notes") or "").strip()
    external = str(
        record.get("TransactionID") or record.get("Id") or record.get("BankTransactionID") or ""
    ).strip()
    if not external:
        external = f"bank:{nominal_code}:{dated}:{amount}:{reference}"[:128]
    return {
        "amount_gbp": round(amount, 2),
        "date": dated,
        "posted_on": dated,
        "description": reference[:256] or f"QuickFile bank {nominal_code}",
        "external_id": external,
        "account_external_id": nominal_code,
        "account_name": account_name,
        "currency": str(record.get("Currency") or "GBP"),
        "scope": FinanceScope.BUSINESS.value,
    }


def _normalize_invoice(record: dict[str, Any], *, cutoff: str) -> dict[str, Any] | None:
    dated = _parse_date(record, "IssueDate", "InvoiceDate", "Date")
    if dated and cutoff and dated < cutoff:
        return None
    amount = _parse_amount(record, "Total", "GrossAmount", "Amount", "InvoiceTotal", "TotalAmount")
    if amount is None or amount == 0:
        return None
    invoice_id = str(
        record.get("InvoiceID") or record.get("Id") or record.get("InvoiceNumber") or ""
    ).strip()
    number = str(record.get("InvoiceNumber") or invoice_id or "invoice").strip()
    client = str(record.get("ClientName") or record.get("CompanyName") or "").strip()
    description = f"Invoice {number}"
    if client:
        description = f"{description} — {client}"
    return {
        "amount_gbp": round(abs(amount), 2),
        "date": dated,
        "posted_on": dated,
        "description": description[:256],
        "external_id": f"qf-inv:{invoice_id or number}"[:128],
        "account_external_id": "quickfile-invoices",
        "account_name": "QuickFile invoices",
        "currency": str(record.get("Currency") or "GBP"),
        "scope": FinanceScope.BUSINESS.value,
    }


def _normalize_purchase(record: dict[str, Any], *, cutoff: str) -> dict[str, Any] | None:
    dated = _parse_date(record, "ReceiptDate", "PurchaseDate", "Date", "IssueDate")
    if dated and cutoff and dated < cutoff:
        return None
    amount = _parse_amount(record, "Total", "GrossAmount", "Amount", "PurchaseTotal", "TotalAmount")
    if amount is None or amount == 0:
        return None
    purchase_id = str(
        record.get("PurchaseID") or record.get("Id") or record.get("ReceiptNumber") or ""
    ).strip()
    number = str(record.get("ReceiptNumber") or purchase_id or "bill").strip()
    supplier = str(record.get("SupplierName") or "").strip()
    description = f"Bill {number}"
    if supplier:
        description = f"{description} — {supplier}"
    return {
        "amount_gbp": -round(abs(amount), 2),
        "date": dated,
        "posted_on": dated,
        "description": description[:256],
        "external_id": f"qf-bill:{purchase_id or number}"[:128],
        "account_external_id": "quickfile-purchases",
        "account_name": "QuickFile purchases",
        "currency": str(record.get("Currency") or "GBP"),
        "scope": FinanceScope.BUSINESS.value,
    }


class QuickFileProvider(BaseFinanceProvider):
    name = "quickfile"

    def __init__(self, config: QuickFileConfig) -> None:
        self._config = config
        self._client = QuickFileClient(config)

    def _ensure_configured(self) -> None:
        if not (
            self._config.account_number and self._config.api_key and self._config.application_id
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
        """Import bank statement lines plus invoice/purchase document headers.

        Bank_Search provides cash movements. Invoice_Search / Purchase_Search return
        document totals (not item lines — those need Invoice_Get / Purchase_Get per
        document and are not bulk-imported). Document rows use distinct external_id
        prefixes (``qf-inv:`` / ``qf-bill:``) so fingerprints never collide with bank
        lines; history budgets that include both may over-count the same economic event.

        Date ranges longer than one year are walked in year-sized chunks so a single
        Bank_Search / Invoice_Search / Purchase_Search call never covers a huge window.
        """
        self._ensure_configured()
        today = datetime.now(timezone.utc).date()
        if since:
            cutoff = since[:10]
        else:
            cutoff = (today - timedelta(days=QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS)).isoformat()
        until = today.isoformat()
        windows = lookback_date_chunks(cutoff, until)
        collected: list[dict[str, Any]] = []
        try:
            accounts = await self._client.fetch_bank_accounts()
        except QuickFileError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc

        for record in accounts:
            code = _nominal_code(record)
            if not code:
                continue
            name = _account_name(record)
            for from_date, to_date in windows:
                rows = await self._client.fetch_bank_transactions(
                    code, from_date=from_date, to_date=to_date
                )
                for item in rows:
                    normalized = _normalize_bank_line(
                        item, nominal_code=code, account_name=name, cutoff=cutoff
                    )
                    if normalized:
                        collected.append(normalized)

        for from_date, to_date in windows:
            invoices = await self._client.fetch_invoices(from_date=from_date, to_date=to_date)
            for item in invoices:
                normalized = _normalize_invoice(item, cutoff=cutoff)
                if normalized:
                    collected.append(normalized)

            purchases = await self._client.fetch_purchases(from_date=from_date, to_date=to_date)
            for item in purchases:
                normalized = _normalize_purchase(item, cutoff=cutoff)
                if normalized:
                    collected.append(normalized)

        return collected

    async def fetch_debtors_gbp(self) -> float:
        """Debtors control balance from the live QuickFile balance sheet."""
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
