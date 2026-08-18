from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.finance import QuickFileConfig
from app.services.quickfile_settings_service import quickfile_settings_service
from app.services.settings_crypto import seal_json


@pytest.mark.asyncio
async def test_quickfile_reads_encrypted_row(monkeypatch: pytest.MonkeyPatch) -> None:
    sealed = seal_json(
        {
            "account_number": "6112345678",
            "api_key": "stored-key",
            "application_id": "stored-app",
        }
    )

    async def fake_row(_db, key: str):
        if key == "quickfile":
            return SimpleNamespace(value=sealed)
        return None

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_row)
    monkeypatch.setattr(
        quickfile_settings_service, "_persist_config", AsyncMock()
    )
    config = await quickfile_settings_service.get_config(None)
    assert config == QuickFileConfig(
        account_number="6112345678",
        api_key="stored-key",
        application_id="stored-app",
    )


@pytest.mark.asyncio
async def test_quickfile_falls_back_to_env_when_decrypt_fails(
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

    async def fake_row(_db, key: str):
        if key == "quickfile":
            return SimpleNamespace(value="enc:v1:gAAAA-not-valid")
        return None

    persist = AsyncMock()
    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_row)
    monkeypatch.setattr(quickfile_settings_service, "_persist_config", persist)
    config = await quickfile_settings_service.get_config(None)
    assert config.account_number == "env-account"
    assert config.api_key == "env-key"
    assert config.application_id == "env-app"
    persist.assert_awaited_once()
    persisted = persist.await_args.args[1]
    assert persisted == QuickFileConfig(
        account_number="env-account",
        api_key="env-key",
        application_id="env-app",
    )


@pytest.mark.asyncio
async def test_quickfile_status_connected_when_env_set(
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

    async def fake_row(_db, key: str):
        return None

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_row)
    monkeypatch.setattr(
        quickfile_settings_service, "_persist_config", AsyncMock()
    )
    status = await quickfile_settings_service.get_status(None)
    assert status.configured is True
    assert status.connected is True
    assert status.api_key_set is True
    assert status.budget_account_external_ids == []


@pytest.mark.asyncio
async def test_quickfile_set_config_does_not_wipe_env_backed_keys_with_blanks(
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

    async def fake_row(_db, key: str):
        return None

    persist = AsyncMock()
    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_row)
    monkeypatch.setattr(quickfile_settings_service, "_persist_config", persist)

    status = await quickfile_settings_service.set_config(
        None,
        QuickFileConfig(account_number="", api_key="", application_id=""),
    )
    assert status.configured is True
    assert status.connected is True
    # Final persist from set_config must keep the env-backed complete config.
    assert persist.await_count >= 1
    last = persist.await_args_list[-1].args[1]
    assert last == QuickFileConfig(
        account_number="env-account",
        api_key="env-key",
        application_id="env-app",
    )


@pytest.mark.asyncio
async def test_quickfile_missing_neon_row_falls_back_to_env(
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

    async def fake_row(_db, key: str):
        return None

    persist = AsyncMock()
    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_row)
    monkeypatch.setattr(quickfile_settings_service, "_persist_config", persist)

    status = await quickfile_settings_service.get_status(None)
    assert status.configured is True
    assert status.connected is True
    persist.assert_awaited()


@pytest.mark.asyncio
async def test_lunchflow_reads_legacy_encrypted_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.finance import LunchFlowConfig
    from app.services.lunchflow_settings_service import lunchflow_settings_service

    sealed = seal_json({"api_key": "legacy-stored-key"})

    async def fake_row(_db, key: str):
        if key == "lunch_flow":
            return SimpleNamespace(value=sealed)
        return None

    monkeypatch.setattr(lunchflow_settings_service, "_get_row", fake_row)
    config = await lunchflow_settings_service.get_config(None)
    assert config == LunchFlowConfig(api_key="legacy-stored-key")
