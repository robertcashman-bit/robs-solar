"""QuickFile full-import flag — satisfied year history, not auto-deep."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.finance.sync_lookback import (
    QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS,
    QUICKFILE_SATISFIED_LOOKBACK_DAYS,
)
from app.services.quickfile_settings_service import (
    _FULL_IMPORT_KEY,
    _FULL_IMPORT_LOOKBACK_KEY,
    is_quickfile_quota_error,
    quickfile_settings_service,
    quota_blocked_until_tomorrow_utc,
)


class _FakeDb:
    def __init__(self, rows: dict[str, str] | None = None) -> None:
        self.rows = dict(rows or {})
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.commits = 0

    async def scalar(self, stmt):  # noqa: ANN001
        return None

    def add(self, row) -> None:  # noqa: ANN001
        self.added.append(row)
        key = getattr(row, "key", None)
        value = getattr(row, "value", None)
        if key is not None and value is not None:
            self.rows[str(key)] = str(value)

    async def delete(self, row) -> None:  # noqa: ANN001
        self.deleted.append(row)
        key = getattr(row, "key", None)
        if key is not None:
            self.rows.pop(str(key), None)

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_needs_full_when_marker_missing_and_no_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(_db, key: str):
        return None

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_get)
    monkeypatch.setattr(
        quickfile_settings_service,
        "existing_quickfile_history",
        AsyncMock(return_value=(0, 0)),
    )
    assert await quickfile_settings_service.needs_full_history_import(_FakeDb()) is True


@pytest.mark.asyncio
async def test_needs_full_false_when_lookback_days_missing_but_history_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing lookback + substantial Neon txs must not deep-import via needs_full."""

    async def fake_get(_db, key: str):
        return None

    marked = AsyncMock()
    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_get)
    monkeypatch.setattr(
        quickfile_settings_service,
        "existing_quickfile_history",
        AsyncMock(return_value=(1382, 365)),
    )
    monkeypatch.setattr(
        quickfile_settings_service, "mark_full_history_imported", marked
    )
    assert await quickfile_settings_service.needs_full_history_import(_FakeDb()) is False
    marked.assert_awaited_once()
    assert marked.await_args.kwargs["lookback_days"] >= QUICKFILE_SATISFIED_LOOKBACK_DAYS


@pytest.mark.asyncio
async def test_needs_full_false_when_prior_lookback_is_one_year(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recorded 365-day import is enough for needs_full — deep extension is separate."""

    async def fake_get(_db, key: str):
        if key == _FULL_IMPORT_KEY:
            return SimpleNamespace(key=key, value="2026-08-18T00:00:00+00:00")
        if key == _FULL_IMPORT_LOOKBACK_KEY:
            return SimpleNamespace(key=key, value="365")
        return None

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_get)
    assert await quickfile_settings_service.needs_full_history_import(_FakeDb()) is False


@pytest.mark.asyncio
async def test_needs_full_false_when_lookback_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(_db, key: str):
        if key == _FULL_IMPORT_KEY:
            return SimpleNamespace(key=key, value="2026-08-18T00:00:00+00:00")
        if key == _FULL_IMPORT_LOOKBACK_KEY:
            return SimpleNamespace(
                key=key, value=str(QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS)
            )
        return None

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_get)
    assert await quickfile_settings_service.needs_full_history_import(_FakeDb()) is False


@pytest.mark.asyncio
async def test_mark_full_history_stores_lookback_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeDb()
    stored: dict[str, str] = {}

    async def fake_get(_db, key: str):
        if key in stored:
            return SimpleNamespace(key=key, value=stored[key])
        return None

    async def fake_set(_db, key: str, value: str) -> None:
        stored[key] = value

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_get)
    monkeypatch.setattr(quickfile_settings_service, "_set_value", fake_set)
    await quickfile_settings_service.mark_full_history_imported(db)
    assert _FULL_IMPORT_KEY in stored
    assert stored[_FULL_IMPORT_LOOKBACK_KEY] == str(QUICKFILE_SATISFIED_LOOKBACK_DAYS)

    await quickfile_settings_service.mark_full_history_imported(
        db, lookback_days=QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS
    )
    assert stored[_FULL_IMPORT_LOOKBACK_KEY] == str(QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS)


@pytest.mark.asyncio
async def test_clear_full_history_import_removes_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = {
        _FULL_IMPORT_KEY: "2026-08-18T00:00:00+00:00",
        _FULL_IMPORT_LOOKBACK_KEY: "365",
    }
    db = _FakeDb(rows)

    async def fake_get(_db, key: str):
        if key in db.rows:
            return SimpleNamespace(key=key, value=db.rows[key])
        return None

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_get)
    await quickfile_settings_service.clear_full_history_import(db)
    assert _FULL_IMPORT_KEY not in db.rows
    assert _FULL_IMPORT_LOOKBACK_KEY not in db.rows
    assert db.commits == 1


@pytest.mark.asyncio
async def test_needs_deep_history_extension_when_lookback_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(_db, key: str):
        return None

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_get)
    assert await quickfile_settings_service.needs_deep_history_extension(_FakeDb()) is True


@pytest.mark.asyncio
async def test_needs_deep_history_extension_when_lookback_one_year(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(_db, key: str):
        if key == _FULL_IMPORT_KEY:
            return SimpleNamespace(key=key, value="2026-08-18T00:00:00+00:00")
        if key == _FULL_IMPORT_LOOKBACK_KEY:
            return SimpleNamespace(key=key, value="365")
        return None

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_get)
    assert await quickfile_settings_service.needs_deep_history_extension(_FakeDb()) is True


@pytest.mark.asyncio
async def test_needs_deep_history_extension_false_when_lookback_two_years(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get(_db, key: str):
        if key == _FULL_IMPORT_KEY:
            return SimpleNamespace(key=key, value="2026-08-18T00:00:00+00:00")
        if key == _FULL_IMPORT_LOOKBACK_KEY:
            return SimpleNamespace(
                key=key, value=str(QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS)
            )
        return None

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_get)
    assert await quickfile_settings_service.needs_deep_history_extension(_FakeDb()) is False


@pytest.mark.asyncio
async def test_quota_error_sets_last_error_keeps_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.quickfile_settings_service.settings.quickfile_account_number",
        "env-account",
    )
    monkeypatch.setattr(
        "app.services.quickfile_settings_service.settings.quickfile_api_key",
        "env-key",
    )
    monkeypatch.setattr(
        "app.services.quickfile_settings_service.settings.quickfile_application_id",
        "env-app",
    )
    stored: dict[str, str] = {}

    async def fake_get(_db, key: str):
        if key in stored:
            return SimpleNamespace(key=key, value=stored[key])
        return None

    async def fake_set(_db, key: str, value: str) -> None:
        stored[key] = value

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_get)
    monkeypatch.setattr(quickfile_settings_service, "_set_value", fake_set)
    monkeypatch.setattr(
        quickfile_settings_service, "_persist_config", AsyncMock()
    )

    assert is_quickfile_quota_error("API request limit exceeded (1000)")
    await quickfile_settings_service.record_error(
        _FakeDb(), "API request limit exceeded (1000)"
    )
    status = await quickfile_settings_service.get_status(_FakeDb())
    assert status.configured is True
    assert status.connected is True
    assert status.last_error and "API request limit exceeded" in status.last_error
    assert status.quota_exhausted_at
    assert quota_blocked_until_tomorrow_utc(status.quota_exhausted_at) is True
