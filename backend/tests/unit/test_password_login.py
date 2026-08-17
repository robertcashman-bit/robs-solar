from app.auth.dependencies import authenticate_user
from app.auth.passwords import get_seed_users
from app.config import settings
from app.schemas.domain import LoginRequest


def test_login_accepts_admin_email_alias(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "secret-pass")
    monkeypatch.setattr(settings, "admin_email", "rob@example.com")
    users = get_seed_users()
    assert "admin" in users
    assert "rob@example.com" in users
    assert authenticate_user(LoginRequest(username="Rob@Example.com", password="secret-pass"))
    assert authenticate_user(LoginRequest(username="admin", password="secret-pass"))
    assert authenticate_user(LoginRequest(username="Rob@Example.com", password="wrong")) is None


def test_login_is_case_insensitive_for_username(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_username", "AdminUser")
    monkeypatch.setattr(settings, "admin_password", "secret-pass")
    monkeypatch.setattr(settings, "admin_email", "")
    assert authenticate_user(LoginRequest(username="adminuser", password="secret-pass"))


def test_default_admin_email_alias_uses_env_password(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "secret-pass")
    monkeypatch.setattr(settings, "admin_email", "robertdavidcashman@gmail.com")
    assert authenticate_user(
        LoginRequest(username="RobertDavidCashman@gmail.com", password="secret-pass")
    )


def test_cors_always_allows_hosted_and_local_origins(monkeypatch) -> None:
    monkeypatch.setattr(settings, "cors_origins", "http://127.0.0.1:3000")
    origins = settings.cors_origin_list
    assert "http://127.0.0.1:3000" in origins
    assert "http://localhost:3000" in origins
    assert "https://robs-solar.vercel.app" in origins
