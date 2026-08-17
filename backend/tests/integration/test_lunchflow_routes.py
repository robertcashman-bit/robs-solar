"""Integration tests for Lunch Flow routes."""

import pytest
from httpx import AsyncClient

from app.integrations.lunchflow_provider import LunchFlowProvider
from tests.conftest import login


@pytest.mark.asyncio
async def test_lunchflow_status_starts_inactive(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    response = await client.get("/finance/integrations/lunchflow/status")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert body["connected"] is False
    assert body["provider"] == "lunchflow"


@pytest.mark.asyncio
async def test_save_and_test_lunchflow(client: AsyncClient, monkeypatch) -> None:
    data = await login(client, "admin", "admin-pass")

    put = await client.put(
        "/finance/integrations/lunchflow/settings",
        json={"api_key": "lf_live_test"},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert put.status_code == 200
    assert put.json()["api_key_set"] is True
    assert put.json()["configured"] is True
    assert put.json()["connected"] is False
    before = await client.get("/finance/integrations")
    lunchflow_before = next(item for item in before.json() if item["id"] == "lunchflow")
    assert lunchflow_before["status"] == "inactive"

    async def fake_test(self):
        return {"ok": True, "account_count": 2}

    monkeypatch.setattr(LunchFlowProvider, "test_connection", fake_test)
    response = await client.post(
        "/finance/integrations/lunchflow/test",
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 200
    assert response.json()["account_count"] == 2

    get = await client.get("/finance/integrations/lunchflow/status")
    assert get.json()["api_key_set"] is True
    assert get.json()["connected"] is True
    integrations = await client.get("/finance/integrations")
    lunchflow = next(item for item in integrations.json() if item["id"] == "lunchflow")
    assert lunchflow["status"] == "active"
