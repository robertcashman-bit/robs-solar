"""OIDC auth helper tests."""

from app.auth.oidc import map_user_from_claims, oidc_configured
from app.config import settings
from app.schemas.domain import UserRole


def test_oidc_configured_requires_all_fields(monkeypatch) -> None:
    monkeypatch.setattr(settings, "oidc_enabled", True)
    monkeypatch.setattr(settings, "oidc_issuer_url", "https://idp.example.com")
    monkeypatch.setattr(settings, "oidc_client_id", "client")
    monkeypatch.setattr(settings, "oidc_client_secret", "secret")
    monkeypatch.setattr(settings, "oidc_redirect_uri", "https://app.example.com/callback")
    assert oidc_configured() is True


def test_map_user_admin_by_email(monkeypatch) -> None:
    monkeypatch.setattr(settings, "oidc_admin_emails", "rob@example.com")
    username, role = map_user_from_claims({"email": "rob@example.com"})
    assert username == "rob"
    assert role == UserRole.ADMIN


def test_map_user_viewer_by_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "oidc_admin_emails", "admin@example.com")
    username, role = map_user_from_claims({"email": "viewer@example.com"})
    assert username == "viewer"
    assert role == UserRole.VIEWER
