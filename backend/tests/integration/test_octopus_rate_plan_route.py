"""Integration tests for Octopus rate-plan route."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_rate_plan_requires_octopus_configured(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.octopus_client import octopus_client

    monkeypatch.setattr(octopus_client, "configured", lambda: False)
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/octopus/rate-plan")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_rate_plan_returns_plan_shape(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.schemas.domain import OctopusRatePlan, RatePlanWindow
    from app.services.octopus_client import octopus_client

    async def fake_plan() -> OctopusRatePlan:
        return OctopusRatePlan(
            configured=True,
            tariff_family="IOG",
            region="J",
            cheap_rate_pence=7.0,
            peak_rate_pence=28.6,
            cheap_windows=[RatePlanWindow(start="23:30", end="05:30")],
            peak_windows=[RatePlanWindow(start="05:30", end="23:30")],
            current_rate_pence=28.6,
            current_is_cheap=False,
        )

    monkeypatch.setattr(octopus_client, "configured", lambda: True)
    monkeypatch.setattr(octopus_client, "get_rate_plan", fake_plan)
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/octopus/rate-plan")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["cheap_rate_pence"] == 7.0
    assert body["peak_rate_pence"] == 28.6
    assert body["cheap_windows"][0]["start"] == "23:30"
