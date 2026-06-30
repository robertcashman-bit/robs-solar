"""Tests for Sunsynk settings read via adapter."""

import json
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.adapters.sunsynk_connect import SunsynkConnectAdapter
from app.config import settings

MOCKS = json.loads(
    (Path(__file__).resolve().parents[1] / "mocks" / "sunsynk_responses.json").read_text()
)

_TEST_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_PUBLIC_KEY_PEM = (
    _TEST_PRIVATE_KEY.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode("utf-8")
)

SN = "2210123456"


@pytest.fixture(autouse=True)
def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sunsynk_username", "user@example.com")
    monkeypatch.setattr(settings, "sunsynk_password", "secret")
    monkeypatch.setattr(settings, "sunsynk_plant_id", "537603")
    monkeypatch.setattr(settings, "sunsynk_inverter_sn", SN)


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/anonymous/publicKey":
        return httpx.Response(200, json={"success": True, "data": TEST_PUBLIC_KEY_PEM})
    if path == "/oauth/token/new":
        return httpx.Response(200, json=MOCKS["token"])
    if path == "/api/v1/plant/537603":
        return httpx.Response(200, json=MOCKS["plant_detail"])
    if path == f"/api/v1/common/setting/{SN}/read":
        return httpx.Response(200, json=MOCKS["settings_read"])
    return httpx.Response(404, json={"success": False})


@pytest.mark.asyncio
async def test_get_inverter_settings_parses_bands_and_permissions() -> None:
    client = httpx.AsyncClient(
        base_url="https://api.test",
        transport=httpx.MockTransport(_handler),
        timeout=5.0,
    )
    adapter = SunsynkConnectAdapter(client=client)
    result = await adapter.get_inverter_settings()
    assert result is not None
    assert result.inverter_sn == SN
    assert result.plant_name == "Greenacre"
    assert result.write_allowed is False
    assert "view-only" in result.write_denied_reason
    assert len(result.bands) == 6
    assert result.bands[0].target_soc_pct == 100
    assert result.diagnosis
