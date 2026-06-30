"""Integration tests for restore-last-known-good flow."""

import pytest
from httpx import AsyncClient

from app.config import settings
from tests.conftest import login


@pytest.mark.asyncio
async def test_restore_after_export_limit_snapshot(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "read_only", False)
    monkeypatch.setattr(settings, "adapter_mode", "simulator")

    data = await login(client, "admin", "admin-pass")

    # Write export limit to create snapshot
    write = await client.post(
        "/controls/export-limit",
        json={"limit_w": 2000},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert write.status_code == 200

    # Change again
    write2 = await client.post(
        "/controls/export-limit",
        json={"limit_w": 3000},
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert write2.status_code == 200

    # Restore
    restore = await client.post(
        "/config/restore-last-known-good",
        headers={"X-CSRF-Token": data["csrf_token"]},
    )
    assert restore.status_code == 200
    body = restore.json()
    assert body["success"] is True
    assert body["restored_snapshot_id"] is not None

    # Audit should contain restore action
    audit = await client.get("/audit")
    assert audit.status_code == 200
    actions = [e["action"] for e in audit.json()["entries"]]
    assert "restore_last_known_good" in actions
