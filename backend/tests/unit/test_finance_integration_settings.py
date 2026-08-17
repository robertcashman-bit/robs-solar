"""Unit tests for QuickFile / Lunch Flow env seed and reconnect."""

from __future__ import annotations

import pytest

from app.config import settings
from app.db.session import SessionLocal
from app.services.lunch_flow_settings_service import lunch_flow_settings_service
from app.services.quickfile_settings_service import quickfile_settings_service


async def _clear_setting(db, key: str) -> None:
    row = await quickfile_settings_service._get_row(db, key)
    if row is not None:
        await db.delete(row)
        await db.commit()


@pytest.mark.asyncio
async def test_quickfile_seed_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "quickfile_account_number", "123456")
    monkeypatch.setattr(settings, "quickfile_api_key", "test-key")
    monkeypatch.setattr(settings, "quickfile_application_id", "app-id")
    async with SessionLocal() as db:
        await _clear_setting(db, "quickfile")
        seeded = await quickfile_settings_service.seed_from_env(db)
        status = await quickfile_settings_service.get_status(db)
    assert seeded is True
    assert status.configured is True
    assert status.connection_state.value == "key_saved"


@pytest.mark.asyncio
async def test_lunch_flow_reconnect_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "lunch_flow_api_key", "lf-secret")
    async with SessionLocal() as db:
        row = await lunch_flow_settings_service._get_row(db, "lunch_flow")
        if row is not None:
            await db.delete(row)
            await db.commit()
        reconnected = await lunch_flow_settings_service.reconnect_from_env(db)
        status = await lunch_flow_settings_service.get_status(db)
    assert reconnected is True
    assert status.configured is True
    assert status.api_key_set is True
