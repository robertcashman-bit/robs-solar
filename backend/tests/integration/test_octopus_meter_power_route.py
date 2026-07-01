"""Integration tests for the /octopus/meter-power route live fields."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_meter_power_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/octopus/meter-power")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_meter_power_returns_live_fields_when_present(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.domain import OctopusMeterPower
    from app.services.octopus_client import octopus_client

    async def fake_estimate() -> OctopusMeterPower:
        return OctopusMeterPower(
            configured=True,
            average_power_w=300.0,
            consumption_kwh=0.15,
            daily_import_kwh=4.2,
            live_available=True,
            live_demand_w=376.0,
        )

    monkeypatch.setattr(octopus_client, "get_meter_power_estimate", fake_estimate)

    await login(client, "viewer", "viewer-pass")
    response = await client.get("/octopus/meter-power")
    assert response.status_code == 200
    body = response.json()
    assert body["live_available"] is True
    assert body["live_demand_w"] == 376.0
    assert body["average_power_w"] == 300.0


@pytest.mark.asyncio
async def test_meter_power_omits_live_gracefully(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.domain import OctopusMeterPower
    from app.services.octopus_client import octopus_client

    async def fake_estimate() -> OctopusMeterPower:
        return OctopusMeterPower(
            configured=True,
            average_power_w=300.0,
            consumption_kwh=0.15,
        )

    monkeypatch.setattr(octopus_client, "get_meter_power_estimate", fake_estimate)

    await login(client, "viewer", "viewer-pass")
    response = await client.get("/octopus/meter-power")
    assert response.status_code == 200
    body = response.json()
    assert body["live_available"] is False
    assert body["live_demand_w"] is None
