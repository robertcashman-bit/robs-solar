import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_auth_status_is_inert_when_energy_is_off(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/integrations/sunsynk/auth-status")
    assert response.status_code == 200
    body = response.json()
    assert body["verification_required"] is False
    assert body["message"] is None


@pytest.mark.asyncio
async def test_submit_verification_code_rejected_when_energy_is_off(
    client: AsyncClient,
) -> None:
    session = await login(client, "admin", "admin-pass")
    response = await client.post(
        "/integrations/sunsynk/verification-code",
        json={"code": "482913"},
        headers={"X-CSRF-Token": session["csrf_token"]},
    )
    assert response.status_code == 400
    assert "not active" in response.json()["detail"].lower()
