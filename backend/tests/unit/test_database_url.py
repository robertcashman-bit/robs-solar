"""Unit tests for hosted database URL resolution."""

from __future__ import annotations

from app.db.session import _postgres_default_sql
from app.db.url import (
    is_ephemeral_sqlite,
    normalize_database_url,
    resolve_database_url,
    uses_neon_pooler,
)


def test_ephemeral_tmp_sqlite_is_detected() -> None:
    assert is_ephemeral_sqlite("sqlite+aiosqlite:////tmp/robs_solar.db") is True
    assert is_ephemeral_sqlite("sqlite+aiosqlite:///./data/robs_solar.db") is False


def test_resolve_prefers_neon_when_database_url_is_tmp_sqlite() -> None:
    resolved = resolve_database_url(
        "sqlite+aiosqlite:////tmp/robs_solar.db",
        "postgresql://user:pass@ep-x-pooler.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
        "postgresql://user:pass@ep-x.aws.neon.tech/neondb?sslmode=require",
    )
    assert resolved.startswith("postgresql+asyncpg://")
    assert "sslmode" not in resolved
    assert "channel_binding" not in resolved
    assert "ssl=require" in resolved
    assert uses_neon_pooler(resolved) is True


def test_resolve_keeps_local_sqlite() -> None:
    url = "sqlite+aiosqlite:///./data/robs_solar.db"
    assert resolve_database_url(url, "postgresql://unused", "") == url


def test_normalize_postgres_scheme() -> None:
    assert normalize_database_url("postgres://u:p@h/db").startswith("postgresql+asyncpg://")


def test_postgres_defaults_for_legacy_columns() -> None:
    assert _postgres_default_sql("scope", "VARCHAR(16)") == "'personal'"
    assert _postgres_default_sql("account_name", "VARCHAR(256)") == "''"
    assert _postgres_default_sql("amount", "FLOAT") == "0"
    assert _postgres_default_sql("is_pending", "BOOLEAN") == "false"
