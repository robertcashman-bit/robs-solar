"""QuickFile Bank_Search / invoice / purchase import helpers."""

from __future__ import annotations

import pytest

from app.integrations.quickfile_client import (
    _bank_search_parameters,
    _extract_records,
    _purchase_search_parameters,
)
from app.integrations.quickfile_provider import (
    QuickFileProvider,
    _normalize_bank_line,
    _normalize_invoice,
    _normalize_purchase,
)
from app.schemas.finance import QuickFileConfig
from app.services.finance.finance_import_service import finance_import_service


def test_bank_search_parameters_include_dates_and_nominal() -> None:
    params = _bank_search_parameters(
        nominal_code="1207",
        return_count=200,
        offset=200,
        from_date="2025-08-18",
        to_date="2026-08-18",
    )
    assert params["NominalCode"] == 1207
    assert params["FromDate"] == "2025-08-18"
    assert params["ToDate"] == "2026-08-18"
    assert params["OrderResultsBy"] == "TransactionDate"


def test_extract_nested_bank_transactions() -> None:
    body = {
        "MetaData": {"RecordsetCount": 1},
        "Transactions": {
            "Transaction": [
                {
                    "TransactionDate": "2026-07-01T00:00:00",
                    "Reference": "TESCO",
                    "Amount": -12.34,
                }
            ]
        },
    }
    rows = _extract_records(body)
    assert len(rows) == 1
    assert rows[0]["Amount"] == -12.34


def test_normalize_bank_invoice_purchase_rows() -> None:
    bank = _normalize_bank_line(
        {
            "TransactionDate": "2026-07-01T00:00:00",
            "Reference": "CARD",
            "Amount": -9.99,
            "TransactionID": "B1",
        },
        nominal_code="1200",
        account_name="Current",
        cutoff="2026-01-01",
    )
    assert bank is not None
    assert bank["amount_gbp"] == -9.99
    assert bank["external_id"] == "B1"
    assert bank["scope"] == "business"

    invoice = _normalize_invoice(
        {
            "IssueDate": "2026-06-15",
            "InvoiceNumber": "INV-1",
            "InvoiceID": 99,
            "Total": 120.0,
            "ClientName": "Acme",
        },
        cutoff="2026-01-01",
    )
    assert invoice is not None
    assert invoice["amount_gbp"] == 120.0
    assert invoice["external_id"] == "qf-inv:99"

    bill = _normalize_purchase(
        {
            "ReceiptDate": "2026-06-16",
            "ReceiptNumber": "QF1",
            "PurchaseID": 7,
            "Total": 40.0,
            "SupplierName": "Tools Co",
        },
        cutoff="2026-01-01",
    )
    assert bill is not None
    assert bill["amount_gbp"] == -40.0
    assert bill["external_id"] == "qf-bill:7"


def test_purchase_search_parameters() -> None:
    params = _purchase_search_parameters(
        return_count=50,
        offset=0,
        receipt_date_from="2026-01-01",
        receipt_date_to="2026-08-01",
    )
    assert params["ReceiptDateFrom"] == "2026-01-01"
    assert params["OrderResultsBy"] == "ReceiptDate"


def test_quickfile_fingerprints_dedupe_across_lookback_overlap() -> None:
    """Overlapping first-sync and incremental windows share fingerprints."""
    row = {
        "posted_on": "2026-07-01",
        "amount_gbp": -12.34,
        "description": "TESCO",
        "account_external_id": "1200",
        "account_name": "Business",
        "external_id": "qf-bank-1",
        "scope": "business",
        "currency": "GBP",
    }
    first, _ = finance_import_service.validate_row(row, source="quickfile")
    second, _ = finance_import_service.validate_row(row, source="quickfile")
    assert first is not None and second is not None
    assert first["fingerprint"] == second["fingerprint"]


@pytest.mark.asyncio
async def test_quickfile_provider_sync_transactions_collects_all_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = QuickFileProvider(
        QuickFileConfig(account_number="1", api_key="k", application_id="a")
    )

    async def fake_accounts():
        return [{"NominalCode": 1200, "Name": "Business Current", "BankType": "CURRENT"}]

    async def fake_bank(code, *, from_date=None, to_date=None):
        assert str(code) == "1200"
        return [
            {
                "TransactionDate": "2026-07-01",
                "Amount": -10,
                "Reference": "CARD",
                "TransactionID": "b1",
            }
        ]

    async def fake_invoices(*, from_date=None, to_date=None, status=None):
        return [
            {
                "IssueDate": "2026-07-02",
                "InvoiceID": 1,
                "InvoiceNumber": "INV1",
                "Total": 50,
            }
        ]

    async def fake_purchases(*, from_date=None, to_date=None):
        return [
            {
                "ReceiptDate": "2026-07-03",
                "PurchaseID": 2,
                "ReceiptNumber": "R1",
                "Total": 8,
            }
        ]

    monkeypatch.setattr(provider._client, "fetch_bank_accounts", fake_accounts)
    monkeypatch.setattr(provider._client, "fetch_bank_transactions", fake_bank)
    monkeypatch.setattr(provider._client, "fetch_invoices", fake_invoices)
    monkeypatch.setattr(provider._client, "fetch_purchases", fake_purchases)

    rows = await provider.sync_transactions(since="2026-06-01")
    assert len(rows) == 3
    sources = {item["account_external_id"] for item in rows}
    assert sources == {"1200", "quickfile-invoices", "quickfile-purchases"}
