"""Unit tests for QuickFile client auth and parsing."""

import hashlib

import pytest

from app.integrations.quickfile_client import (
    QuickFileError,
    _bank_accounts_search_parameters,
    _client_search_parameters,
    _invoice_search_parameters,
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
