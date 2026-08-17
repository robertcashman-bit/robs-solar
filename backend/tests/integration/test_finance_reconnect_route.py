"""Integration test for hosted finance reconnect."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from tests.conftest import login


@pytest.mark.asyncio
async def test_reconnect_uses_hosted_env_keys(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "read_only", False)
    monkeypatch.setattr(settings, "quickfile_account_number", "123456")
    monkeypatch.setattr(settings, "quickfile_api_key", "test-key")
    monkeypatch.setattr(settings, "quickfile_application_id", "app-id")
    monkeypatch.setattr(settings, "lunch_flow_api_key", "lf-secret")
    data = await login(client, "admin", "admin-pass")
    response = await client.post(
        "/finance/integrations/reconnect",
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["quickfile_seeded"] is True
    assert body["lunch_flow_seeded"] is True
    assert body["quickfile"]["configured"] is True
    assert body["lunch_flow"]["configured"] is True
    assert "Reconnected" in body["message"]
