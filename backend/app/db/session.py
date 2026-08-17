from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.database_url import (
    is_ephemeral_sqlite,
    is_postgres_url,
    normalise_database_url,
    postgres_connect_args,
    resolve_database_url,
)
from app.db.models import Base

__all__ = [
    "SessionLocal",
    "engine",
    "get_db",
    "init_db",
    "is_postgres_url",
    "resolve_database_url",
]


def _ensure_sqlite_dir(database_url: str) -> None:
    """Create the parent directory for a file-backed SQLite DB.

    A fresh checkout (e.g. CI) has no ./data directory, so SQLite would fail
    with "unable to open database file". Creating it up front keeps tests and
    first-run deploys working without committing the database itself.
    """
    if not database_url.startswith("sqlite"):
        return
    db_path = database_url.split("///", 1)[-1]
    if not db_path or db_path == ":memory:":
        return
    parent = Path(db_path).expanduser().parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)


def _normalise_database_url(database_url: str) -> str:
    """Back-compat alias — prefer normalise_database_url."""
    return normalise_database_url(database_url)


_RESOLVED_DATABASE_URL = resolve_database_url()
_NORMALISED_DATABASE_URL = normalise_database_url(_RESOLVED_DATABASE_URL)
_ensure_sqlite_dir(_RESOLVED_DATABASE_URL)
_ENGINE_KWARGS: dict = {
    "echo": False,
    "connect_args": postgres_connect_args(_RESOLVED_DATABASE_URL),
}
if is_postgres_url(_RESOLVED_DATABASE_URL):
    _ENGINE_KWARGS["poolclass"] = NullPool
    if "neon.tech" in _NORMALISED_DATABASE_URL and "-pooler" in _NORMALISED_DATABASE_URL:
        _ENGINE_KWARGS["connect_args"] = {
            **_ENGINE_KWARGS["connect_args"],
            "statement_cache_size": 0,
        }
engine = create_async_engine(_NORMALISED_DATABASE_URL, **_ENGINE_KWARGS)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def database_backend() -> str:
    return engine.url.get_backend_name()


def database_is_persistent() -> bool:
    if is_postgres_url(_RESOLVED_DATABASE_URL):
        return True
    return not is_ephemeral_sqlite(_RESOLVED_DATABASE_URL)


def _scalar_default_sql(column, *, dialect_name: str) -> str | None:
    """Render a DEFAULT clause for scalar column defaults (not callables)."""
    default = column.default
    if default is None or not getattr(default, "is_scalar", False):
        return None
    arg = default.arg
    if callable(arg):
        return None
    if isinstance(arg, bool):
        if dialect_name == "postgresql":
            return "TRUE" if arg else "FALSE"
        return "1" if arg else "0"
    if isinstance(arg, (int, float)):
        return str(arg)
    if isinstance(arg, str):
        return f"'{arg}'"
    return None


def _migrate_missing_columns(connection) -> None:
    """Add columns introduced after initial deploy (SQLite and Postgres)."""
    inspector = inspect(connection)
    dialect_name = connection.dialect.name
    for table_name, table in Base.metadata.tables.items():
        if table_name not in inspector.get_table_names():
            continue
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name in existing:
                continue
            col_type = column.type.compile(dialect=connection.dialect)
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}"
            default_sql = _scalar_default_sql(column, dialect_name=dialect_name)
            if default_sql is not None:
                sql = f"{sql} DEFAULT {default_sql}"
            connection.execute(text(sql))
    if "finance_liabilities" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("finance_liabilities")}
        if "interest_rate_known" in cols:
            known = "TRUE" if dialect_name == "postgresql" else "1"
            connection.execute(
                text(
                    "UPDATE finance_liabilities "
                    f"SET interest_rate_known = {known} WHERE interest_rate_known IS NULL"
                )
            )
    for index_sql in (
        "CREATE INDEX IF NOT EXISTS ix_finance_accounts_active_scope "
        "ON finance_accounts (is_active, scope)",
        "CREATE INDEX IF NOT EXISTS ix_finance_liabilities_active "
        "ON finance_liabilities (is_active)",
        "CREATE INDEX IF NOT EXISTS ix_finance_budget_plans_active "
        "ON finance_budget_plans (is_active)",
        "CREATE INDEX IF NOT EXISTS ix_cashflow_forecast_confirmed_date "
        "ON cashflow_forecast (is_confirmed, forecast_date)",
        "CREATE INDEX IF NOT EXISTS ix_finance_transactions_active_posted "
        "ON finance_transactions (is_deleted, posted_on)",
    ):
        table = index_sql.split(" ON ", 1)[1].split(" ", 1)[0]
        if table in inspector.get_table_names():
            connection.execute(text(index_sql))


def _sqlite_scalar_default_sql(column) -> str | None:
    """Back-compat alias used by existing SQLite migration tests."""
    return _scalar_default_sql(column, dialect_name="sqlite")


def _migrate_sqlite_columns(connection) -> None:
    """Back-compat alias used by existing SQLite migration tests."""
    _migrate_missing_columns(connection)


def _postgres_default_sql(column_name: str, col_type: str) -> str:
    if column_name == "scope":
        return "'personal'"
    lowered = col_type.lower()
    if "bool" in lowered:
        return "false"
    if any(token in lowered for token in ("int", "numeric", "float", "double", "real", "decimal")):
        return "0"
    if any(token in lowered for token in ("time", "date")):
        return "CURRENT_TIMESTAMP"
    return "''"


def _compat_legacy_not_null_columns(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    inspector = inspect(connection)
    for table_name, table in Base.metadata.tables.items():
        if table_name not in inspector.get_table_names():
            continue
        model_cols = {column.name for column in table.columns}
        for constraint in inspector.get_unique_constraints(table_name):
            cols = set(constraint.get("column_names") or [])
            name = constraint.get("name")
            if name and cols and not cols.issubset(model_cols):
                connection.execute(
                    text(f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS "{name}"')
                )
        for index in inspector.get_indexes(table_name):
            cols = set(index.get("column_names") or [])
            name = index.get("name")
            if name and index.get("unique") and cols and not cols.issubset(model_cols):
                connection.execute(text(f'DROP INDEX IF EXISTS "{name}"'))
        for column in inspector.get_columns(table_name):
            name = column["name"]
            if name in model_cols or column.get("nullable", True):
                continue
            default = _postgres_default_sql(name, str(column.get("type") or ""))
            connection.execute(
                text(f'ALTER TABLE "{table_name}" ALTER COLUMN "{name}" DROP NOT NULL')
            )
            connection.execute(
                text(
                    f'ALTER TABLE "{table_name}" ALTER COLUMN "{name}" SET DEFAULT {default}'
                )
            )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_missing_columns)
        await conn.run_sync(_compat_legacy_not_null_columns)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
