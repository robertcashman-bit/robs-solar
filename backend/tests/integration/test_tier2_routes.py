"""Integration tests for tier 2-4 routes."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_reconciliation_route_viewer(client: AsyncClient, monkeypatch) -> None:
    from app.services import octopus_client as octopus_module

    monkeypatch.setattr(octopus_module.octopus_client, "configured", lambda: False)
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/reconciliation?range=day")
    assert response.status_code == 200
    body = response.json()
    assert "meter_import_kwh" in body
    assert body["configured"] is False


@pytest.mark.asyncio
async def test_notification_settings_admin(client: AsyncClient) -> None:
    session = await login(client, "admin", "admin-pass")
    get_resp = await client.get("/settings/notifications")
    assert get_resp.status_code == 200
    put_resp = await client.put(
        "/settings/notifications",
        json={
            "webhook_url": "https://example.com/hook",
            "smtp_host": "",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_password": "",
            "email_to": "test@example.com",
            "export_price_threshold_pence": 18,
            "categories": get_resp.json()["categories"],
        },
        headers={"X-CSRF-Token": session["csrf_token"]},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["email_to"] == "test@example.com"


@pytest.mark.asyncio
async def test_safety_settings_admin(client: AsyncClient) -> None:
    session = await login(client, "admin", "admin-pass")
    response = await client.put(
        "/config/safety",
        json={"read_only": True},
        headers={"X-CSRF-Token": session["csrf_token"]},
    )
    assert response.status_code == 200
    assert response.json()["read_only"] is True


@pytest.mark.asyncio
async def test_rules_crud(client: AsyncClient) -> None:
    session = await login(client, "admin", "admin-pass")
    headers = {"X-CSRF-Token": session["csrf_token"]}
    create = await client.post(
        "/controls/rules",
        json={
            "id": "",
            "name": "Test rule",
            "enabled": True,
            "condition": "soc_below",
            "condition_value": 15,
            "action": "raise_alert",
            "cooldown_minutes": 30,
        },
        headers=headers,
    )
    assert create.status_code == 200
    rule_id = create.json()["rules"][0]["id"]
    listed = await client.get("/controls/rules")
    assert listed.status_code == 200
    assert any(r["id"] == rule_id for r in listed.json()["rules"])
    deleted = await client.delete(f"/controls/rules/{rule_id}", headers=headers)
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_ev_status_route(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/ev/status")
    assert response.status_code == 200
    assert "car_charging_likely" in response.json()


@pytest.mark.asyncio
async def test_charge_window_route(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/charge-window")
    assert response.status_code == 200
    body = response.json()
    assert "importing_on_cheap_window" in body
    assert "message" in body


@pytest.mark.asyncio
async def test_sell_opportunity_route(client: AsyncClient, monkeypatch) -> None:
    from app.services import octopus_client as octopus_module

    monkeypatch.setattr(octopus_module.octopus_client, "configured", lambda: False)
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/sell-opportunity")
    assert response.status_code == 200
    body = response.json()
    assert "worth_selling" in body
    assert body["configured"] is False
