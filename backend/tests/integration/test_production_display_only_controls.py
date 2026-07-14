"""Production display-only lock for energy control writes."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_production_blocks_export_limit_write(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    # Login while still in development so the session cookie is not Secure-only.
    data = await login(client, "admin", "admin-pass")
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "read_only", False)
    monkeypatch.setattr(settings, "enable_live_writes", True)

    response = await client.post(
        "/controls/export-limit",
        json={"limit_w": 3000},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 403
    assert "display-only" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_production_blocks_auto_schedule_write(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    data = await login(client, "admin", "admin-pass")
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "read_only", False)

    response = await client.post(
        "/controls/auto-schedule",
        json={"enabled": True, "soc_floor_pct": 20},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_production_blocks_rules_mutation(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    data = await login(client, "admin", "admin-pass")
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "read_only", False)

    response = await client.post(
        "/controls/rules",
        json={
            "id": "prod-block",
            "name": "Should not create",
            "enabled": True,
            "condition": "soc_below",
            "condition_value": 15,
            "action": "raise_alert",
            "cooldown_minutes": 30,
        },
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 403
