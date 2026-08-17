from types import SimpleNamespace

import pytest

from app.schemas.domain import OctopusConfig
from app.services.octopus_settings_service import octopus_settings_service


@pytest.mark.asyncio
async def test_get_config_ignores_empty_json(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_row(_db):
        return SimpleNamespace(value="")

    monkeypatch.setattr(octopus_settings_service, "_get_row", fake_row)
    config = await octopus_settings_service.get_config(None)
    assert isinstance(config, OctopusConfig)


@pytest.mark.asyncio
async def test_get_config_ignores_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_row(_db):
        return SimpleNamespace(value="not-json")

    monkeypatch.setattr(octopus_settings_service, "_get_row", fake_row)
    config = await octopus_settings_service.get_config(None)
    assert isinstance(config, OctopusConfig)
