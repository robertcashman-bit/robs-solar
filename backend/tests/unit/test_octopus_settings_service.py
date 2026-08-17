"""Unit tests for Octopus settings auto-seed and discover."""

import json

import pytest
from sqlalchemy import delete

from app.config import settings
from app.db.models import AppSettingRow
from app.db.session import SessionLocal
from app.schemas.domain import OctopusConfig
from app.services.octopus_client import octopus_client
from app.services.octopus_settings_service import OctopusSettingsService


@pytest.mark.asyncio
async def test_load_into_client_seeds_from_env_and_discovers_meter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = OctopusSettingsService()
    monkeypatch.setattr(settings, "octopus_api_key", "sk_live_test")
    monkeypatch.setattr(settings, "octopus_account_number", "A-TEST1234")
    monkeypatch.setattr(settings, "octopus_mpan", "")
    monkeypatch.setattr(settings, "octopus_meter_serial", "")
    monkeypatch.setattr(settings, "octopus_region", "J")

    async def fake_discover(api_key: str, account_number: str) -> dict[str, str]:
        assert api_key == "sk_live_test"
        assert account_number == "A-TEST1234"
        return {
            "mpan": "1900033149437",
            "meter_serial": "24L3288488",
            "region": "J",
            "account_number": account_number,
            "import_tariff_code": "",
        }

    monkeypatch.setattr(octopus_client, "discover", fake_discover)

    async with SessionLocal() as db:
        await db.execute(delete(AppSettingRow).where(AppSettingRow.key == "octopus"))
        await db.commit()
        await service.load_into_client(db)
        row = (
            await db.execute(
                __import__("sqlalchemy").select(AppSettingRow).where(AppSettingRow.key == "octopus")
            )
        ).scalar_one()
        stored = OctopusConfig.model_validate(json.loads(row.value))
        assert stored.mpan == "1900033149437"
        assert stored.meter_serial == "24L3288488"
        assert stored.region == "J"

    assert octopus_client.credentials.mpan == "1900033149437"
    assert octopus_client.credentials.meter_serial == "24L3288488"
