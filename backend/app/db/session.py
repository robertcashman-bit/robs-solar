from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.models import Base
from app.db.url import (
    is_postgres_url,
    is_sqlite_url,
    resolve_database_url,
    uses_neon_pooler,
)

DATABASE_URL = resolve_database_url(
    settings.database_url,
    settings.neon_database_url,
    settings.neon_database_url_unpooled,
)


def _ensure_sqlite_dir(database_url: str) -> None:
    """Create the parent directory for a file-backed SQLite DB.

    A fresh checkout (e.g. CI) has no ./data directory, so SQLite would fail
    with "unable to open database file". Creating it up front keeps tests and
    first-run deploys working without committing the database itself.
    """
    if not is_sqlite_url(database_url):
        return
    db_path = database_url.split("///", 1)[-1]
    if not db_path or db_path == ":memory:":
        return
    parent = Path(db_path).expanduser().parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)


def _engine_kwargs(database_url: str) -> dict:
    kwargs: dict = {"echo": False}
    if not is_postgres_url(database_url):
        return kwargs
    # Serverless invocations must not hold a connection pool across requests.
    kwargs["poolclass"] = NullPool
    if uses_neon_pooler(database_url):
        kwargs["connect_args"] = {"statement_cache_size": 0}
    return kwargs


_ensure_sqlite_dir(DATABASE_URL)
engine = create_async_engine(DATABASE_URL, **_engine_kwargs(DATABASE_URL))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def database_backend() -> str:
    return engine.url.get_backend_name()


def database_is_persistent() -> bool:
    if is_postgres_url(DATABASE_URL):
        return True
    if not is_sqlite_url(DATABASE_URL):
        return False
    return "/tmp/" not in DATABASE_URL and ":memory:" not in DATABASE_URL


def _migrate_missing_columns(connection) -> None:
    """Add columns introduced after initial deploy."""
    inspector = inspect(connection)
    for table_name, table in Base.metadata.tables.items():
        if table_name not in inspector.get_table_names():
            continue
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name in existing:
                continue
            col_type = column.type.compile(dialect=connection.dialect)
            connection.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}")
            )


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
    """Relax leftover Neon columns/constraints so slimmer model inserts succeed."""
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


def _compat_legacy_lunchflow_source(connection) -> None:
    """Older rows used source=lunchflow; this app's enum is lunch_flow."""
    inspector = inspect(connection)
    if "finance_accounts" not in inspector.get_table_names():
        return
    connection.execute(
        text(
            "UPDATE finance_accounts SET is_active = false, source = 'lunch_flow' "
            "WHERE source = 'lunchflow'"
        )
    )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_missing_columns)
        await conn.run_sync(_compat_legacy_not_null_columns)
        await conn.run_sync(_compat_legacy_lunchflow_source)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
