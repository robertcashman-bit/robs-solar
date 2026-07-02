"""Integration tests for QuickFile finance routes."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_quickfile_status_unconfigured(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/finance/integrations/quickfile/status")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False


@pytest.mark.asyncio
async def test_quickfile_save_and_test(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    csrf = data["csrf_token"]

    save = await client.put(
        "/finance/integrations/quickfile/settings",
        json={
            "account_number": "123456",
            "api_key": "test-api-key",
            "application_id": "test-app-id",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert save.status_code == 200
    assert save.json()["configured"] is True

    async def fake_test(self):  # noqa: ANN001
        return {"ok": True, "sample_count": 1}

    from app.integrations.quickfile_provider import QuickFileProvider

    monkeypatch.setattr(QuickFileProvider, "test_connection", fake_test)
    test = await client.post(
        "/finance/integrations/quickfile/test",
        headers={"X-CSRF-Token": csrf},
    )
    assert test.status_code == 200
    assert test.json()["ok"] is True
