"""Integration tests for Octopus dispatch route."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_dispatches_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/octopus/dispatches")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dispatches_returns_off_peak_window(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.domain import DispatchResponse, OffPeakWindow
    from app.services.octopus_client import octopus_client

    async def fake_dispatches() -> DispatchResponse:
        return DispatchResponse(
            off_peak_window=OffPeakWindow(start="23:30", end="05:30"),
            planned=[],
            completed=[],
            tariff_family="IOG",
        )

    monkeypatch.setattr(octopus_client, "configured", lambda: True)
    monkeypatch.setattr(octopus_client, "get_dispatches", fake_dispatches)

    await login(client, "viewer", "viewer-pass")
    response = await client.get("/octopus/dispatches")
    assert response.status_code == 200
    body = response.json()
    assert body["off_peak_window"]["start"] == "23:30"
    assert body["tariff_family"] == "IOG"
