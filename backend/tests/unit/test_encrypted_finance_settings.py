from types import SimpleNamespace

import pytest

from app.schemas.finance import LunchFlowConfig, QuickFileConfig
from app.services.lunchflow_settings_service import lunchflow_settings_service
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

    monkeypatch.setattr(quickfile_settings_service, "_get_row", fake_row)
    config = await quickfile_settings_service.get_config(None)
    assert config.account_number == "env-account"
    assert config.api_key == "env-key"


@pytest.mark.asyncio
async def test_lunchflow_reads_legacy_encrypted_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sealed = seal_json({"api_key": "legacy-stored-key"})

    async def fake_row(_db, key: str):
        if key == "lunch_flow":
            return SimpleNamespace(value=sealed)
        return None

    monkeypatch.setattr(lunchflow_settings_service, "_get_row", fake_row)
    config = await lunchflow_settings_service.get_config(None)
    assert config == LunchFlowConfig(api_key="legacy-stored-key")
