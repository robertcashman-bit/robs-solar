from app.db.database_url import (
    is_ephemeral_sqlite,
    is_postgres_url,
    normalise_database_url,
    postgres_connect_args,
    resolve_database_url,
)
from app.services.finance.finance_seed_service import is_live_finance_database


def test_normalise_postgres_urls() -> None:
    assert normalise_database_url("postgres://u:p@h/db").startswith("postgresql+asyncpg://")
    assert normalise_database_url("postgresql://u:p@h/db").startswith("postgresql+asyncpg://")
    assert normalise_database_url("sqlite+aiosqlite:///./data/robs_solar.db").startswith("sqlite")
    neon = "postgresql://u:p@ep-x.lhr.aws.neon.tech/db?sslmode=require&channel_binding=require"
    cleaned = normalise_database_url(neon)
    assert cleaned.startswith("postgresql+asyncpg://")
    assert "sslmode" not in cleaned
    assert "channel_binding" not in cleaned
    assert postgres_connect_args(neon) == {"ssl": True}


def test_ephemeral_sqlite_detection() -> None:
    assert is_ephemeral_sqlite("sqlite+aiosqlite:////tmp/robs_solar.db") is True
    assert is_ephemeral_sqlite("sqlite+aiosqlite:///./data/robs_solar.db") is False
    assert is_ephemeral_sqlite("postgresql+asyncpg://u:p@h/db") is False


def test_resolve_keeps_sqlite_when_flagged(monkeypatch) -> None:
    monkeypatch.setenv("FINANCE_KEEP_SQLITE", "true")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ROBS_FINANCE_DATABASE_URL", "postgresql://u:p@h/db")
    assert (
        resolve_database_url("sqlite+aiosqlite:////tmp/robs_solar.db")
        == "sqlite+aiosqlite:////tmp/robs_solar.db"
    )


def test_resolve_uses_prefixed_neon_in_production(monkeypatch) -> None:
    monkeypatch.delenv("FINANCE_KEEP_SQLITE", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ROBS_FINANCE_DATABASE_URL", "postgresql://u:p@h/robs")
    resolved = resolve_database_url("sqlite+aiosqlite:////tmp/robs_solar.db")
    assert is_postgres_url(resolved)
    assert resolved.endswith("/robs")


def test_resolve_does_not_override_local_file_sqlite(monkeypatch) -> None:
    monkeypatch.delenv("FINANCE_KEEP_SQLITE", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ROBS_FINANCE_DATABASE_URL", "postgresql://u:p@h/robs")
    local = "sqlite+aiosqlite:///./data/robs_solar.db"
    assert resolve_database_url(local) == local


def test_live_db_check_accepts_postgres() -> None:
    assert is_live_finance_database("postgresql://u:p@ep-live.lhr.aws.neon.tech/neondb") is True
    assert is_live_finance_database("postgresql://u:p@h/pytest_db") is False
    assert is_live_finance_database("sqlite+aiosqlite:///./data/robs_solar.db") is True
    assert is_live_finance_database("sqlite+aiosqlite:///./data/test_robs_solar.db") is False
