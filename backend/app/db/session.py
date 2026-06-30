from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base


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


_ensure_sqlite_dir(settings.database_url)
engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def _migrate_sqlite_columns(connection) -> None:
    """Add columns introduced after initial deploy (SQLite has no ALTER TABLE batch)."""
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


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.database_url.startswith("sqlite"):
            await conn.run_sync(_migrate_sqlite_columns)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
