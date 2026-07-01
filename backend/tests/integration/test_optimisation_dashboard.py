"""Integration tests for optimisation dashboard endpoints."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_warnings_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/metrics/warnings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_warnings_returns_list(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/warnings")
    assert response.status_code == 200
    body = response.json()
    assert "warnings" in body
    assert "status_headline" in body


@pytest.mark.asyncio
async def test_recommendations_list(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/recommendations")
    assert response.status_code == 200
    assert "recommendations" in response.json()


@pytest.mark.asyncio
async def test_optimisation_mode_defaults_read_only(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/optimisation/mode")
    assert response.status_code == 200
    assert response.json()["mode"] == "read_only"


@pytest.mark.asyncio
async def test_savings_history(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/savings-history?range=month")
    assert response.status_code == 200
    body = response.json()
    assert "points" in body
    assert "projected_annual_gbp" in body
