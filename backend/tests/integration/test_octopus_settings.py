"""Tests for Octopus settings + discover routes."""

import pytest
from httpx import AsyncClient

from app.services.octopus_client import octopus_client
from tests.conftest import login


@pytest.mark.asyncio
async def test_octopus_settings_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/octopus/settings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_viewer_cannot_read_octopus_settings(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/octopus/settings")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_put_then_get_masks_key(client: AsyncClient) -> None:
    data = await login(client, "admin", "admin-pass")
    put = await client.put(
        "/octopus/settings",
        json={
            "api_key": "sk_live_testkey",
            "account_number": "A-TEST1234",
            "mpan": "1900000000000",
            "meter_serial": "TESTSERIAL",
            "region": "j",
        },
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert put.status_code == 200
    body = put.json()
    assert body["api_key_set"] is True
    assert body["configured"] is True
    assert body["region"] == "J"
    assert "api_key" not in body

    get = await client.get("/octopus/settings")
    assert get.status_code == 200
    got = get.json()
    assert got["account_number"] == "A-TEST1234"
    assert got["mpan"] == "1900000000000"
    assert "api_key" not in got

    # Live client received the credentials.
    assert octopus_client.configured() is True
    assert octopus_client.credentials.agile_tariff_code.endswith("-J")


@pytest.mark.asyncio
async def test_discover_returns_meter_details(client: AsyncClient, monkeypatch) -> None:
    data = await login(client, "admin", "admin-pass")

    async def fake_discover(api_key: str, account_number: str) -> dict[str, str]:
        return {
            "account_number": account_number,
            "mpan": "1900033149437",
            "meter_serial": "24L3288488",
            "region": "J",
        }

    monkeypatch.setattr(octopus_client, "discover", fake_discover)
    response = await client.post(
        "/octopus/discover",
        json={"api_key": "sk_live_x", "account_number": "A-DBCBC021"},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mpan"] == "1900033149437"
    assert body["meter_serial"] == "24L3288488"
    assert body["region"] == "J"
