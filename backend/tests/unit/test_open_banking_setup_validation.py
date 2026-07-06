"""Unit tests for Open Banking setup validation."""

from app.schemas.finance import OpenBankingConfig, OpenBankingSetupSaveRequest
from app.services.open_banking_setup_validation import (
    classify_test_error,
    map_setup_request_to_config,
    run_test_validation,
    success_test_result,
    validate_config,
    validate_redirect_url,
)
from app.integrations.base import IntegrationNotConfiguredError


def _empty_config() -> OpenBankingConfig:
    return OpenBankingConfig()


def test_map_enable_banking_fields() -> None:
    req = OpenBankingSetupSaveRequest(
        provider="enable_banking",
        client_id="app-123",
        client_secret="-----BEGIN RSA PRIVATE KEY-----\nabc",
        redirect_url="https://example.com/open-banking/callback",
        environment="live",
        country="gb",
    )
    config = map_setup_request_to_config(req, _empty_config())
    assert config.provider == "enable_banking"
    assert config.application_id == "app-123"
    assert "BEGIN RSA PRIVATE KEY" in config.private_key_pem
    assert config.environment == "PRODUCTION"
    assert config.redirect_url == "https://example.com/open-banking/callback"


def test_map_gocardless_fields() -> None:
    req = OpenBankingSetupSaveRequest(
        provider="gocardless",
        client_id="secret-id",
        client_secret="secret-key",
        redirect_url="http://127.0.0.1:3000/open-banking/callback",
        environment="sandbox",
    )
    config = map_setup_request_to_config(req, _empty_config())
    assert config.provider == "gocardless"
    assert config.secret_id == "secret-id"
    assert config.secret_key == "secret-key"
    assert config.environment == "SANDBOX"


def test_validate_missing_enable_credentials() -> None:
    config = OpenBankingConfig(provider="enable_banking", redirect_url="https://x.com/cb")
    errors = validate_config(config, existing=_empty_config())
    assert any("Client ID is missing" in e for e in errors)
    assert any("Client Secret is missing" in e for e in errors)


def test_validate_redirect_http_in_live() -> None:
    error = validate_redirect_url(
        "http://127.0.0.1:3000/open-banking/callback",
        "PRODUCTION",
    )
    assert error is not None
    assert "https" in error


def test_validate_redirect_invalid_url() -> None:
    error = validate_redirect_url("not-a-url", "SANDBOX")
    assert error is not None
    assert "valid web address" in error


def test_run_test_validation_missing_credentials() -> None:
    config = OpenBankingConfig(provider="enable_banking")
    result = run_test_validation(config, _empty_config())
    assert result is not None
    assert result.status == "missing_credentials"


def test_classify_inactive_application() -> None:
    result = classify_test_error(
        IntegrationNotConfiguredError("Enable Banking 400: Application is not active")
    )
    assert result.status == "further_bank_authorisation_required"


def test_classify_rejected_credentials() -> None:
    result = classify_test_error(
        IntegrationNotConfiguredError("Enable Banking 401: Invalid JWT signature")
    )
    assert result.status == "provider_rejected_credentials"


def test_success_test_result() -> None:
    result = success_test_result({"ok": True, "application_name": "Rob Finance"})
    assert result.status == "connected_successfully"
    assert "Rob Finance" in result.message
