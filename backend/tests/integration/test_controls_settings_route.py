"""Tests for GET /controls/settings."""

import json
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient

from app.adapters.sunsynk_connect import SunsynkConnectAdapter
from app.config import settings
from tests.conftest import login

MOCKS = json.loads(
    (Path(__file__).resolve().parents[1] / "mocks" / "sunsynk_responses.json").read_text()
)


@pytest.mark.asyncio
async def test_settings_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/controls/settings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_settings_returns_parsed_tou_for_sunsynk(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await login(client, "viewer", "viewer-pass")
    monkeypatch.setattr(settings, "adapter_mode", "sunsynk_connect")

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    sn = "2210123456"

    monkeypatch.setattr(settings, "sunsynk_inverter_sn", sn)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/anonymous/publicKey":
            return httpx.Response(200, json={"success": True, "data": pem})
        if path == "/oauth/token/new":
            return httpx.Response(200, json=MOCKS["token"])
        if path == "/api/v1/plant/537603":
            return httpx.Response(200, json=MOCKS["plant_detail"])
        if path == f"/api/v1/common/setting/{sn}/read":
            return httpx.Response(200, json=MOCKS["settings_read"])
        return httpx.Response(404, json={"success": False})

    mock_client = httpx.AsyncClient(
        base_url="https://api.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
    )
    adapter = SunsynkConnectAdapter(client=mock_client)
    monkeypatch.setattr("app.routes.controls.get_adapter", lambda: adapter)

    response = await client.get("/controls/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["inverter_sn"] == sn
    assert body["bands"][1]["target_soc_pct"] == 19
    assert body["write_allowed"] is False
