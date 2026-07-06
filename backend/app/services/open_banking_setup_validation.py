"""Validation and mapping for the plain-English Open Banking setup form."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.enable_banking_client import EnableBankingError
from app.schemas.finance import (
    OpenBankingConfig,
    OpenBankingSetupSaveRequest,
    OpenBankingTestResult,
    OpenBankingTestStatus,
)

_PROVIDER_LABELS = {
    "enable_banking": "Enable Banking",
    "gocardless": "GoCardless / Nordigen",
}


def map_setup_request_to_config(
    req: OpenBankingSetupSaveRequest,
    existing: OpenBankingConfig,
) -> OpenBankingConfig:
    """Map UI fields to internal OpenBankingConfig, preserving unset secrets."""
    environment = "PRODUCTION" if req.environment == "live" else "SANDBOX"
    country = req.country.strip().lower() or "gb"
    base = existing.model_copy(
        update={
            "provider": req.provider,
            "redirect_url": req.redirect_url.strip(),
            "environment": environment,  # type: ignore[arg-type]
            "country": country,
            "scopes": req.scopes.strip() or "accounts,transactions",
            "webhook_url": req.webhook_url.strip(),
        }
    )
    if req.provider == "enable_banking":
        base.application_id = req.client_id.strip()
        if req.client_secret.strip():
            base.private_key_pem = req.client_secret.strip()
        base.secret_id = ""
        base.secret_key = ""
    else:
        base.secret_id = req.client_id.strip()
        if req.client_secret.strip():
            base.secret_key = req.client_secret.strip()
        base.application_id = ""
        base.private_key_pem = ""
    return base


def validate_redirect_url(url: str, environment: str) -> str | None:
    """Return a plain-English error message, or None if valid."""
    trimmed = url.strip()
    if not trimmed:
        return "Redirect URL is missing — paste the callback URL from your provider dashboard"
    parsed = urlparse(trimmed)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "Redirect URL is not a valid web address — it should look like https://your-app.com/open-banking/callback"
    if environment == "PRODUCTION" and parsed.scheme != "https":
        return "Redirect URL must use https:// when Environment is Live"
    return None


def validate_config(
    config: OpenBankingConfig,
    *,
    existing: OpenBankingConfig,
) -> list[str]:
    """Return human-readable validation errors (empty list = OK)."""
    errors: list[str] = []
    label = _PROVIDER_LABELS.get(config.provider, config.provider)

    if config.provider == "enable_banking":
        if not config.application_id:
            errors.append(
                "Client ID is missing — paste your Application ID from Enable Control Panel "
                "(Your app → Application ID)"
            )
        has_key = bool(config.private_key_pem or existing.private_key_pem)
        if not has_key:
            errors.append(
                "Client Secret is missing — paste the contents of your private.pem file "
                "(Enable Banking uses a certificate key, not a password)"
            )
    elif config.provider == "gocardless":
        if not config.secret_id:
            errors.append(
                "Client ID is missing — paste your Secret ID from the GoCardless / Nordigen dashboard"
            )
        has_secret = bool(config.secret_key or existing.secret_key)
        if not has_secret:
            errors.append(
                "Client Secret is missing — paste your Secret key from the GoCardless dashboard"
            )

    redirect_error = validate_redirect_url(config.redirect_url, config.environment)
    if redirect_error:
        errors.append(redirect_error)

    if not config.country or len(config.country) != 2:
        errors.append("Bank country is missing — choose a two-letter country code (e.g. GB for United Kingdom)")

    return errors


def classify_test_error(exc: Exception) -> OpenBankingTestResult:
    """Turn provider errors into plain-English test results."""
    message = str(exc)
    lowered = message.lower()

    if isinstance(exc, IntegrationNotConfiguredError):
        if "not active" in lowered or "activate" in lowered:
            return OpenBankingTestResult(
                status="further_bank_authorisation_required",
                message=(
                    "Your provider accepted the credentials but the app is not fully active yet. "
                    "In Enable Control Panel, open your app and complete activation by linking accounts."
                ),
                details={"provider_error": message},
            )
        if "not configured" in lowered or "missing" in lowered:
            return OpenBankingTestResult(
                status="missing_credentials",
                message=message,
            )
        if "redirect" in lowered:
            return OpenBankingTestResult(
                status="invalid_redirect_url",
                message=message,
            )

    if isinstance(exc, EnableBankingError):
        if "not active" in lowered or "activate" in lowered:
            return OpenBankingTestResult(
                status="further_bank_authorisation_required",
                message=(
                    "Your provider accepted the credentials but the app is not fully active yet. "
                    "In Enable Control Panel, open your app and complete activation by linking accounts."
                ),
                details={"provider_error": message},
            )
        if any(token in lowered for token in ("401", "403", "unauthorized", "forbidden", "jwt", "signature")):
            return OpenBankingTestResult(
                status="provider_rejected_credentials",
                message=(
                    "The provider rejected your credentials. Check that Client ID and Client Secret "
                    "match your provider dashboard and that you uploaded the matching public certificate."
                ),
                details={"provider_error": message},
            )
        if "redirect" in lowered or "callback" in lowered:
            return OpenBankingTestResult(
                status="invalid_redirect_url",
                message=(
                    "The redirect URL does not match what is registered with your provider. "
                    "Copy the exact callback URL into both this form and your provider app settings."
                ),
                details={"provider_error": message},
            )

    if re.search(r"\b401\b|\b403\b", message):
        return OpenBankingTestResult(
            status="provider_rejected_credentials",
            message="The provider rejected your credentials. Double-check Client ID and Client Secret.",
            details={"provider_error": message},
        )

    return OpenBankingTestResult(
        status="provider_rejected_credentials",
        message=f"Connection test failed: {message}",
        details={"provider_error": message},
    )


def run_test_validation(config: OpenBankingConfig, existing: OpenBankingConfig) -> OpenBankingTestResult | None:
    """Pre-flight checks before calling the provider API."""
    errors = validate_config(config, existing=existing)
    if errors:
        return OpenBankingTestResult(
            status="missing_credentials",
            message=errors[0] if len(errors) == 1 else "Some required settings are missing.",
            details={"errors": "; ".join(errors)},
        )
    redirect_error = validate_redirect_url(config.redirect_url, config.environment)
    if redirect_error:
        return OpenBankingTestResult(
            status="invalid_redirect_url",
            message=redirect_error,
        )
    return None


def success_test_result(provider_result: dict[str, object]) -> OpenBankingTestResult:
    app_name = str(provider_result.get("application_name") or "")
    institution_count = provider_result.get("institution_count")
    if app_name:
        message = f"Connected successfully to {app_name}."
    elif institution_count is not None:
        message = f"Connected successfully ({institution_count} banks available)."
    else:
        message = "Connected successfully — your provider credentials and redirect URL look correct."
    details: dict[str, str] = {}
    if app_name:
        details["application_name"] = app_name
    if institution_count is not None:
        details["institution_count"] = str(institution_count)
    return OpenBankingTestResult(
        status="connected_successfully",
        message=message,
        details=details,
    )
