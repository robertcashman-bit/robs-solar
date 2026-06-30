"""Tests for GET /capabilities."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_capabilities_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/capabilities")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_capabilities_simulator_mode(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["adapter"]["mode"] == "simulator"
    assert body["data_source"] == "simulated"
    assert body["read_only"] is True
    assert body["enable_live_writes"] is False
    assert "export_limit" in body["adapter"]["supported_writes"]
