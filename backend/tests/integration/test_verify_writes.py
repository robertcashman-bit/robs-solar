"""Control write verification on simulator."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_tou_write_verified_on_simulator(client: AsyncClient) -> None:
    from app.services.safety_settings_service import safety_settings_service

    session = await login(client, "admin", "admin-pass")
    await client.put(
        "/config/safety",
        json={"read_only": False, "enable_live_writes": True},
        headers={"X-CSRF-Token": session["csrf_token"]},
    )
    safety_settings_service._overrides = {
        "read_only": False,
        "enable_live_writes": True,
    }
    response = await client.post(
        "/controls/tou",
        json={
            "bands": [
                {
                    "slot": 1,
                    "start": "00:00",
                    "target_soc_pct": 100,
                    "grid_charge_enabled": True,
                    "power_w": 3000,
                }
            ]
        },
        headers={"X-CSRF-Token": session["csrf_token"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["verified"] is True
