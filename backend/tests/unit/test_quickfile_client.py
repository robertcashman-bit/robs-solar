"""Unit tests for QuickFile client auth and parsing."""

import hashlib

import pytest

from app.integrations.quickfile_client import (
    QuickFileError,
    _bank_accounts_search_parameters,
    _client_search_parameters,
    _extract_records,
    _invoice_search_parameters,
    _parse_balance_amount,
    build_quickfile_auth,
    parse_quickfile_response,
)
from app.schemas.finance import QuickFileConfig


def test_bank_accounts_search_parameters_include_required_fields() -> None:
    params = _bank_accounts_search_parameters()
    assert params["OrderResultsBy"] == "Position"
    assert "CURRENT" in params["AccountTypes"]["AccountType"]
    assert "CREDITCARD" in params["AccountTypes"]["AccountType"]


def test_client_search_parameters_include_ordering() -> None:
    params = _client_search_parameters(return_count=1)
    assert params["OrderResultsBy"] == "CompanyName"
    assert params["OrderDirection"] == "ASC"


def test_invoice_search_parameters_use_status_not_invoice_status() -> None:
    params = _invoice_search_parameters(return_count=50, status="UNPAID")
    assert params["Status"] == "UNPAID"
    assert "InvoiceStatus" not in params
    assert params["OrderResultsBy"] == "InvoiceNumber"


def test_parse_balance_amount_from_account_balances() -> None:
    assert _parse_balance_amount({"NominalCode": 1207, "Amount": -5056.61}) == -5056.61
    assert _parse_balance_amount({"Amount": 202.8}) == 202.8


def test_extract_account_balances_records() -> None:
    body = {
        "AccountBalances": [
            {"NominalCode": 1207, "Amount": -5056.61},
            {"NominalCode": 1259, "Amount": -6884.63},
        ]
    }
    records = _extract_records(body)
    assert len(records) == 2
    assert _parse_balance_amount(records[0]) == -5056.61


def test_build_quickfile_auth_md5() -> None:
    config = QuickFileConfig(
        account_number="123456",
        api_key="secret-key",
        application_id="app-id",
    )
    auth = build_quickfile_auth(config, submission_number="sub-1")
    expected = hashlib.md5(b"123456secret-keysub-1").hexdigest().lower()
    assert auth["md5_value"] == expected
    assert auth["account_number"] == "123456"
    assert auth["application_id"] == "app-id"


def test_build_quickfile_auth_missing_fields() -> None:
    with pytest.raises(QuickFileError, match="missing"):
        build_quickfile_auth(QuickFileConfig())


def test_parse_quickfile_response_success() -> None:
    raw = """
    {
      "Client_Search": {
        "Header": {"Status": "OK"},
        "Body": {"Record": [{"ClientID": "1"}]}
      }
    }
    """
    body = parse_quickfile_response(200, raw)
    assert body["Record"][0]["ClientID"] == "1"


def test_parse_quickfile_response_api_error() -> None:
    raw = '{"Errors": {"Error": {"Message": "Bad request"}}}'
    with pytest.raises(QuickFileError, match="Bad request"):
        parse_quickfile_response(200, raw)
