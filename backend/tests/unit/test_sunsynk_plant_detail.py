"""Tests for Sunsynk inverter SN auto-discovery from plant inverters list."""

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


@pytest.fixture(autouse=True)
def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sunsynk_username", "user@example.com")
    monkeypatch.setattr(settings, "sunsynk_password", "secret")
    monkeypatch.setattr(settings, "sunsynk_plant_id", "537603")
    monkeypatch.setattr(settings, "sunsynk_inverter_sn", "")


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/anonymous/publicKey":
        return httpx.Response(200, json={"success": True, "data": TEST_PUBLIC_KEY_PEM})
    if path == "/oauth/token/new":
        return httpx.Response(200, json=MOCKS["token"])
    if path == "/api/v1/plant/537603/inverters":
        return httpx.Response(200, json=MOCKS["inverters"])
    return httpx.Response(404, json={"success": False})


@pytest.mark.asyncio
async def test_inverter_sn_discovered_from_inverters_list() -> None:
    client = httpx.AsyncClient(
        base_url="https://api.test",
        transport=httpx.MockTransport(_handler),
        timeout=5.0,
    )
    adapter = SunsynkConnectAdapter(client=client)
    sn = await adapter._inverter_sn()
    assert sn == "2210123456"
