import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_robs_solar.db")
os.environ.setdefault("READ_ONLY", "true")
os.environ.setdefault("ENABLE_LIVE_WRITES", "false")
os.environ.setdefault("SUNSYNK_ENABLE_UNVERIFIED_WRITES", "false")
os.environ.setdefault("ADAPTER_MODE", "simulator")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin-pass")
os.environ.setdefault("VIEWER_USERNAME", "viewer")
os.environ.setdefault("VIEWER_PASSWORD", "viewer-pass")
os.environ.setdefault("METRICS_SAMPLER_ENABLED", "false")
os.environ.setdefault("AI_ENABLED", "false")

from app.db.session import init_db
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def setup_db() -> AsyncGenerator[None, None]:
    await init_db()
    yield


@pytest_asyncio.fixture(autouse=True)
async def reset_safety_settings() -> AsyncGenerator[None, None]:
    from sqlalchemy import delete

    from app.db.models import AppSettingRow
    from app.db.session import SessionLocal
    from app.services.safety_settings_service import safety_settings_service

    async with SessionLocal() as db:
        await db.execute(delete(AppSettingRow).where(AppSettingRow.key == "safety_settings"))
        await db.commit()
    safety_settings_service._overrides = None
    yield
    async with SessionLocal() as db:
        await db.execute(delete(AppSettingRow).where(AppSettingRow.key == "safety_settings"))
        await db.commit()
    safety_settings_service._overrides = None


@pytest_asyncio.fixture(autouse=True)
async def reset_write_rate_limiter() -> AsyncGenerator[None, None]:
    # The limiter is a process-wide singleton; clear it so write counts from one
    # test don't bleed into the next and trip a spurious 429.
    from app.middleware.rate_limit import write_rate_limiter

    write_rate_limiter._events.clear()
    yield


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def login(client: AsyncClient, username: str, password: str) -> dict:
    response = await client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    data = response.json()
    return data
