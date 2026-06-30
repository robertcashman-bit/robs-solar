"""Tests for /octopus/prices, /octopus/tariff, and discover error mapping."""

import httpx
import pytest
from httpx import AsyncClient

from app.services.octopus_client import OctopusTariffInfo, octopus_client
from tests.conftest import login

_AGILE = [
    {
        "valid_from": "2026-06-29T07:30:00Z",
        "valid_to": "2026-06-29T08:00:00Z",
        "value_inc_vat": 18.6,
    },
    {
        "valid_from": "2026-06-29T08:00:00Z",
        "valid_to": "2026-06-29T08:30:00Z",
        "value_inc_vat": -2.0,
    },
]

_TARIFF = OctopusTariffInfo(
    import_tariff_code="E-1R-IOG-KDP-FIX-12M-25-06-20-J",
    import_product_code="IOG-KDP-FIX-12M-25-06-20",
    import_display_name="IOG",
    import_rate_pence=22.38,
    export_tariff_code="E-1R-OUTGOING-VAR-24-10-26-J",
    export_product_code="OUTGOING-VAR-24-10-26",
    export_display_name="OUTGOING",
    export_rate_pence=12.0,
    is_variable=False,
    tariff_family="IOG",
    region="J",
)


@pytest.mark.asyncio
async def test_prices_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/octopus/prices")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_prices_503_when_unconfigured(client: AsyncClient, monkeypatch) -> None:
    await login(client, "viewer", "viewer-pass")
    monkeypatch.setattr(octopus_client, "configured", lambda: False)
    response = await client.get("/octopus/prices")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_prices_returns_tariff_and_agile(client: AsyncClient, monkeypatch) -> None:
    await login(client, "viewer", "viewer-pass")
    monkeypatch.setattr(octopus_client, "configured", lambda: True)

    async def fake_tariff() -> OctopusTariffInfo:
        return _TARIFF

    async def fake_agile(hours: int = 24) -> list[dict]:
        return _AGILE

    monkeypatch.setattr(octopus_client, "get_tariff_info", fake_tariff)
    monkeypatch.setattr(octopus_client, "get_agile_rates", fake_agile)

    response = await client.get("/octopus/prices")
    assert response.status_code == 200
    body = response.json()
    assert body["tariff"]["import_rate_pence"] == pytest.approx(22.38)
    assert body["tariff"]["tariff_family"] == "IOG"
    assert body["agile"]["current"]["value_inc_vat"] == pytest.approx(18.6)
    assert body["agile"]["plunge_pricing"] is True
    # Back-compat: top-level agile fields remain for the scheduler overlay.
    assert body["rates"][0]["valid_from"] == "2026-06-29T07:30:00Z"


@pytest.mark.asyncio
async def test_tariff_route_returns_rates(client: AsyncClient, monkeypatch) -> None:
    await login(client, "viewer", "viewer-pass")
    monkeypatch.setattr(octopus_client, "configured", lambda: True)

    async def fake_tariff() -> OctopusTariffInfo:
        return _TARIFF

    monkeypatch.setattr(octopus_client, "get_tariff_info", fake_tariff)
    response = await client.get("/octopus/tariff")
    assert response.status_code == 200
    body = response.json()
    assert body["import_rate_pence"] == pytest.approx(22.38)
    assert body["export_rate_pence"] == pytest.approx(12.0)


@pytest.mark.asyncio
async def test_discover_maps_auth_error_to_400(client: AsyncClient, monkeypatch) -> None:
    data = await login(client, "admin", "admin-pass")

    async def fake_discover(api_key: str, account_number: str) -> dict:
        request = httpx.Request("GET", "https://api.octopus.energy/v1/accounts/A-X/")
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("unauthorised", request=request, response=response)

    monkeypatch.setattr(octopus_client, "discover", fake_discover)
    response = await client.post(
        "/octopus/discover",
        json={"api_key": "bad", "account_number": "A-X"},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_discover_maps_connection_error_to_502(client: AsyncClient, monkeypatch) -> None:
    data = await login(client, "admin", "admin-pass")

    async def fake_discover(api_key: str, account_number: str) -> dict:
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(octopus_client, "discover", fake_discover)
    response = await client.post(
        "/octopus/discover",
        json={"api_key": "x", "account_number": "A-X"},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 502
