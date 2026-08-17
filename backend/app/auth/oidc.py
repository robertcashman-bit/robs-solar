"""OIDC SSO helpers."""

from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import settings
from app.schemas.domain import UserRole

_STATE_SALT = "oidc-state"
_MAX_STATE_AGE_SECONDS = 600


class OidcNotConfiguredError(Exception):
    pass


class OidcAuthError(Exception):
    pass


def oidc_configured() -> bool:
    return bool(
        settings.oidc_enabled
        and settings.oidc_issuer_url
        and settings.oidc_client_id
        and settings.oidc_client_secret
        and settings.oidc_redirect_uri
    )


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt=_STATE_SALT)


def create_state() -> str:
    return _serializer().dumps({"nonce": secrets.token_urlsafe(16)})


def verify_state(state: str) -> None:
    try:
        _serializer().loads(state, max_age=_MAX_STATE_AGE_SECONDS)
    except BadSignature as exc:
        raise OidcAuthError("Invalid or expired OIDC state") from exc


async def discover_metadata() -> dict[str, Any]:
    issuer = settings.oidc_issuer_url.rstrip("/")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{issuer}/.well-known/openid-configuration")
    if response.status_code >= 400:
        raise OidcAuthError(f"OIDC discovery failed: {response.text}")
    return response.json()


async def build_login_redirect(state: str) -> str:
    if not oidc_configured():
        raise OidcNotConfiguredError("OIDC is not configured")
    metadata = await discover_metadata()
    auth_endpoint = metadata.get("authorization_endpoint")
    if not auth_endpoint:
        raise OidcAuthError("OIDC metadata missing authorization_endpoint")
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": "openid email profile",
        "state": state,
    }
    return f"{auth_endpoint}?{urlencode(params)}"


async def exchange_code(code: str) -> dict[str, Any]:
    if not oidc_configured():
        raise OidcNotConfiguredError("OIDC is not configured")
    metadata = await discover_metadata()
    token_endpoint = metadata.get("token_endpoint")
    if not token_endpoint:
        raise OidcAuthError("OIDC metadata missing token_endpoint")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.oidc_redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
            },
        )
    if response.status_code >= 400:
        raise OidcAuthError(f"OIDC token exchange failed: {response.text}")
    return response.json()


async def fetch_userinfo(access_token: str) -> dict[str, Any]:
    metadata = await discover_metadata()
    userinfo_endpoint = metadata.get("userinfo_endpoint")
    if not userinfo_endpoint:
        raise OidcAuthError("OIDC metadata missing userinfo_endpoint")
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            userinfo_endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code >= 400:
        raise OidcAuthError(f"OIDC userinfo failed: {response.text}")
    return response.json()


def map_user_from_claims(claims: dict[str, Any]) -> tuple[str, UserRole]:
    email = str(claims.get("email") or claims.get("preferred_username") or claims.get("sub") or "")
    if not email:
        raise OidcAuthError("OIDC userinfo missing email/sub")
    username = email.split("@", 1)[0]
    role = UserRole.ADMIN if email.lower() in settings.oidc_admin_email_list else UserRole.VIEWER
    return username, role
