"""Resolve the live finance database URL without overwriting DATABASE_URL.

Hosted Vercel still has DATABASE_URL=sqlite:///tmp/... for compatibility.
A prefixed Neon URL (ROBS_FINANCE_DATABASE_URL) is used at runtime in
production when that sqlite path is ephemeral. Tests keep SQLite.
"""

from __future__ import annotations

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DURABLE_URL_ENV_KEYS = (
    "ROBS_FINANCE_DATABASE_URL",
    "ROBS_FINANCE_POSTGRES_URL",
)


def is_postgres_url(database_url: str) -> bool:
    return database_url.startswith("postgresql") or database_url.startswith("postgres")


def is_ephemeral_sqlite(database_url: str) -> bool:
    if is_postgres_url(database_url):
        return False
    if not database_url.startswith("sqlite"):
        return False
    return "/tmp/" in database_url or ":memory:" in database_url


_ASYNCPG_DROP_QUERY_KEYS = {"sslmode", "channel_binding"}


def normalise_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        database_url = "postgresql+asyncpg://" + database_url[len("postgres://") :]
    elif database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
        database_url = "postgresql+asyncpg://" + database_url[len("postgresql://") :]
    if "+asyncpg" in database_url:
        parts = urlsplit(database_url)
        kept = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in _ASYNCPG_DROP_QUERY_KEYS
        ]
        database_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment)
        )
    return database_url


def postgres_connect_args(database_url: str) -> dict[str, object]:
    if not is_postgres_url(database_url):
        return {}
    lowered = database_url.lower()
    if "sslmode=" in lowered or "channel_binding=" in lowered or "neon.tech" in lowered:
        return {"ssl": True}
    return {}


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def resolve_database_url(configured: str | None = None) -> str:
    from app.config import settings

    url = configured if configured is not None else settings.database_url
    if _truthy("FINANCE_KEEP_SQLITE"):
        return url
    if is_postgres_url(url):
        return url
    app_env = (os.environ.get("APP_ENV") or settings.app_env or "").lower()
    if app_env != "production":
        return url
    if not is_ephemeral_sqlite(url):
        return url
    for key in DURABLE_URL_ENV_KEYS:
        alt = os.environ.get(key, "").strip()
        if alt and is_postgres_url(alt):
            return alt
    return url
