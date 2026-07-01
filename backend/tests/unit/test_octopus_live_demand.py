"""Tests for Octopus Home Mini live demand + device detection.

These mock the Kraken GraphQL transport and the token fetch so they never
touch the network.
"""

import httpx
import pytest

from app.services.octopus_client import KRAKEN_GRAPHQL, OctopusClient, OctopusCredentials


def _graphql_client(response_json: dict) -> OctopusClient:
    client = OctopusClient()
    client.update_credentials(
        OctopusCredentials(api_key="k", account_number="A-TEST", region="J")
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == KRAKEN_GRAPHQL
        return httpx.Response(200, json=response_json)

    client._graphql_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=5.0
    )

    async def fake_token() -> str:
        return "token"

    client._obtain_kraken_token = fake_token  # type: ignore[assignment]
    return client


@pytest.mark.asyncio
async def test_get_smart_device_ids_extracts_electricity_device() -> None:
    client = _graphql_client(
        {
            "data": {
                "account": {
                    "electricityAgreements": [
                        {
                            "meterPoint": {
                                "meters": [
                                    {"smartDevices": [{"deviceId": "mini-123"}]}
                                ]
                            }
                        }
                    ]
                }
            }
        }
    )
    devices = await client.get_smart_device_ids()
    assert devices == {"electricity": "mini-123"}


@pytest.mark.asyncio
async def test_get_smart_device_ids_empty_when_no_home_mini() -> None:
    client = _graphql_client(
        {
            "data": {
                "account": {
                    "electricityAgreements": [
                        {"meterPoint": {"meters": [{"smartDevices": []}]}}
                    ]
                }
            }
        }
    )
    assert await client.get_smart_device_ids() == {}


@pytest.mark.asyncio
async def test_get_live_demand_parses_latest_row() -> None:
    client = _graphql_client(
        {
            "data": {
                "smartMeterTelemetry": [
                    {"readAt": "2026-07-01T19:00:00Z", "demand": 310.0},
                    {"readAt": "2026-07-01T19:00:10Z", "demand": 376.4},
                ]
            }
        }
    )
    client.credentials.device_id = "mini-123"
    demand = await client.get_live_demand()
    assert demand.available is True
    assert demand.demand_w == pytest.approx(376.4)
    assert demand.read_at is not None
    assert demand.read_at.year == 2026


@pytest.mark.asyncio
async def test_get_live_demand_unavailable_without_device() -> None:
    client = _graphql_client({"data": {"smartMeterTelemetry": []}})
    # No device_id and detection returns nothing.

    async def no_devices() -> dict:
        return {}

    client.get_smart_device_ids = no_devices  # type: ignore[assignment]
    demand = await client.get_live_demand()
    assert demand.available is False
    assert demand.demand_w is None


@pytest.mark.asyncio
async def test_get_live_demand_unavailable_when_no_rows() -> None:
    client = _graphql_client({"data": {"smartMeterTelemetry": []}})
    client.credentials.device_id = "mini-123"
    demand = await client.get_live_demand()
    assert demand.available is False


@pytest.mark.asyncio
async def test_get_meter_power_estimate_merges_live_demand() -> None:
    from app.schemas.domain import OctopusLiveDemand, OctopusMeterPower

    client = OctopusClient()
    client.update_credentials(
        OctopusCredentials(
            api_key="k",
            account_number="A-TEST",
            mpan="1900000000002",
            meter_serial="IMPORTSER",
            device_id="mini-123",
        )
    )

    async def fake_settled() -> OctopusMeterPower:
        return OctopusMeterPower(
            configured=True,
            average_power_w=300.0,
            consumption_kwh=0.15,
            daily_import_kwh=4.2,
        )

    async def fake_live() -> OctopusLiveDemand:
        return OctopusLiveDemand(available=True, demand_w=376.0)

    client._settled_meter_power = fake_settled  # type: ignore[assignment]
    client.get_live_demand = fake_live  # type: ignore[assignment]

    result = await client.get_meter_power_estimate()
    assert result.configured is True
    assert result.average_power_w == pytest.approx(300.0)
    assert result.live_available is True
    assert result.live_demand_w == pytest.approx(376.0)
