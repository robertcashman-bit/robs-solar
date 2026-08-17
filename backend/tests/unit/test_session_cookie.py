"""Session cookie flags must survive same-host /backend rewrites on Vercel."""

import pytest
from httpx import AsyncClient

from app.auth.sessions import SESSION_COOKIE
from app.config import settings


def _set_cookie_headers(response) -> list[str]:
    return [value for key, value in response.headers.multi_items() if key.lower() == "set-cookie"]


def _cookie_value(header: str) -> str:
    return header.split(";", 1)[0].split("=", 1)[1]


def _assert_host_only_session_cookie(header: str, *, secure: bool) -> None:
    lower = header.lower()
    assert header.startswith(f"{SESSION_COOKIE}=")
    assert "httponly" in lower
    assert "path=/" in lower
    assert "samesite=lax" in lower
    # Domain on vercel.app is a public-suffix landmine — host-only only.
    assert "domain=" not in lower
    if secure:
        assert "secure" in lower


@pytest.mark.asyncio
async def test_login_set_cookie_via_backend_prefix(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    response = await client.post(
        "/backend/auth/login",
        json={"username": "admin", "password": "admin-pass"},
    )
    assert response.status_code == 200
    cookies = _set_cookie_headers(response)
    assert len(cookies) == 1
    _assert_host_only_session_cookie(cookies[0], secure=True)
    assert response.headers.get("cache-control") == "private, no-store"

    # httpx won't auto-store Secure cookies on the fixture's http:// base URL —
    # send the cookie explicitly the way the browser would on https://robs-solar.vercel.app.
    token = _cookie_value(cookies[0])
    me = await client.get(
        "/backend/auth/me",
        headers={"Cookie": f"{SESSION_COOKIE}={token}"},
    )
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "admin"


@pytest.mark.asyncio
async def test_magic_code_verify_set_cookie_via_backend_prefix(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import delete

    from app.db.models import AppSettingRow
    from app.db.session import SessionLocal

    # Dev delivery works outside production; cookie_secure is forced True below.
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "magic_code_enabled", True)
    monkeypatch.setattr(settings, "magic_code_admin_emails", "rob@example.com")
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "public_app_url", "https://robs-solar.vercel.app")
    monkeypatch.setenv("VERCEL", "1")  # hosted Secure even when APP_ENV=development

    async with SessionLocal() as db:
        await db.execute(delete(AppSettingRow).where(AppSettingRow.key.like("auth.magic.%")))
        await db.commit()

    request = await client.post(
        "/backend/auth/magic-code/request",
        json={"email": "rob@example.com"},
    )
    assert request.status_code == 200
    code = request.json()["dev_code"]
    assert code

    verify = await client.post(
        "/backend/auth/magic-code/verify",
        json={"email": "rob@example.com", "code": code},
    )
    assert verify.status_code == 200
    cookies = _set_cookie_headers(verify)
    assert len(cookies) == 1
    _assert_host_only_session_cookie(cookies[0], secure=True)
    assert verify.headers.get("cache-control") == "private, no-store"

    token = _cookie_value(cookies[0])
    me = await client.get(
        "/backend/auth/me",
        headers={"Cookie": f"{SESSION_COOKIE}={token}"},
    )
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "rob"


def test_cookie_secure_on_vercel_even_if_app_env_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setenv("VERCEL", "1")
    assert settings.cookie_secure is True
    monkeypatch.delenv("VERCEL", raising=False)
    assert settings.cookie_secure is False
