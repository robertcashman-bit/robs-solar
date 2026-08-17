"""Public solar/energy HTTP surface must stay unmounted."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import login

ENERGY_PATHS = [
    "/sunsynk/plant",
    "/octopus/prices",
    "/metrics/live",
    "/controls/settings",
    "/forecast/today",
    "/capabilities",
    "/alerts",
    "/tariff/settings",
    "/ai/status",
]


@pytest.mark.asyncio
async def test_energy_routes_are_not_mounted(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    for path in ENERGY_PATHS:
        response = await client.get(path)
        assert response.status_code == 404, f"{path} should be removed, got {response.status_code}"


@pytest.mark.asyncio
async def test_finance_health_has_no_plant_id(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data_source"] == "finance"
    assert body.get("plant_id") in (None, "")
