"""Resolve and normalise the SQLAlchemy database URL.

Hosted Vercel still ships `DATABASE_URL=sqlite+aiosqlite:////tmp/...`.
When that ephemeral URL is present, prefer the Neon `ROBS_FINANCE_*` URLs.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_EPHEMERAL_MARKERS = ("/tmp/", ":memory:")


def is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite")


def is_postgres_url(url: str) -> bool:
    return url.startswith("postgresql") or url.startswith("postgres://")


def is_ephemeral_sqlite(url: str) -> bool:
    if not is_sqlite_url(url):
        return False
    return any(marker in url for marker in _EPHEMERAL_MARKERS)


def uses_neon_pooler(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    return "-pooler" in host


def resolve_database_url(
    database_url: str,
    neon_url: str = "",
    neon_unpooled_url: str = "",
) -> str:
    source = database_url
    if is_ephemeral_sqlite(database_url):
        source = neon_url or neon_unpooled_url or database_url
    return normalize_database_url(source)


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    parsed = urlsplit(url)
    if "asyncpg" not in parsed.scheme:
        return url
    query: list[tuple[str, str]] = []
    ssl_value = ""
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "sslmode":
            ssl_value = value
            continue
        if key in {"channel_binding", "connect_timeout"}:
            continue
        query.append((key, value))
    if ssl_value and not any(key == "ssl" for key, _ in query):
        query.append(("ssl", "require" if ssl_value != "disable" else "disable"))
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )
