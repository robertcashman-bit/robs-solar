from collections.abc import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base

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
