"""Unit tests for Home Assistant adapter writes."""

from unittest.mock import AsyncMock

import pytest

from app.adapters.home_assistant import HomeAssistantAdapter
from app.config import settings
from app.schemas.domain import (
    ExportLimitRequest,
    InverterMode,
    OperatingModeRequest,
    ScheduleAction,
    ScheduleRequest,
    ScheduleWindow,
)


def _mock_response():
    return type("R", (), {"raise_for_status": lambda self: None})()


@pytest.mark.asyncio
async def test_ha_export_limit_service_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ha_base_url", "http://ha.test")
    monkeypatch.setattr(settings, "ha_token", "token")
    monkeypatch.setattr(settings, "ha_service_export_limit", "script.set_export_limit")
    monkeypatch.setattr(settings, "ha_entity_export_limit", "sensor.export_limit")
    adapter = HomeAssistantAdapter()
    adapter._client.post = AsyncMock(return_value=_mock_response())
    result = await adapter.set_export_limit(ExportLimitRequest(limit_w=5000))
    assert result["status"] == "ok"
    adapter._client.post.assert_awaited_once_with(
        "/api/services/script/set_export_limit",
        json={"limit_w": 5000, "entity_id": "sensor.export_limit"},
    )


@pytest.mark.asyncio
async def test_ha_operating_mode_service_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ha_base_url", "http://ha.test")
    monkeypatch.setattr(settings, "ha_token", "token")
    monkeypatch.setattr(settings, "ha_service_operating_mode", "script.set_mode")
    monkeypatch.setattr(settings, "ha_entity_inverter_mode", "select.inverter_mode")
    adapter = HomeAssistantAdapter()
    adapter._client.post = AsyncMock(return_value=_mock_response())
    await adapter.set_operating_mode(OperatingModeRequest(mode=InverterMode.SELF_USE))
    adapter._client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_ha_schedule_service_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ha_base_url", "http://ha.test")
    monkeypatch.setattr(settings, "ha_token", "token")
    monkeypatch.setattr(settings, "ha_service_schedule", "script.set_schedule")
    adapter = HomeAssistantAdapter()
    adapter._client.post = AsyncMock(return_value=_mock_response())
    await adapter.set_schedule(
        ScheduleRequest(
            windows=[
                ScheduleWindow(
                    start="00:00",
                    end="05:30",
                    action=ScheduleAction.CHARGE,
                    target_soc_pct=100,
                )
            ]
        )
    )
    adapter._client.post.assert_awaited_once()
