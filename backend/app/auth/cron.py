"""Authentication for scheduled cron invocations (e.g. Vercel Cron)."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import settings


def require_cron_secret(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    """Verify Vercel Cron `Authorization: Bearer <CRON_SECRET>` header."""
    secret = settings.cron_secret.strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduled sync is not configured on this server",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    token = authorization.removeprefix("Bearer ").strip()
    if token != secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
