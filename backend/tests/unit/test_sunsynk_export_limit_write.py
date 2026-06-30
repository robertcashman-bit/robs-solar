"""Tests for Sunsynk export-limit write using fixture-backed discovered endpoint."""

import json
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.adapters.sunsynk_connect import SunsynkConnectAdapter
from app.config import settings
from app.schemas.domain import ExportLimitRequest, UnsupportedWriteError

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
READ_PATH = f"/api/v1/common/setting/{SN}/read"
WRITE_PATH = f"/api/v1/common/setting/{SN}/set"


@pytest.fixture(autouse=True)
def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sunsynk_username", "user@example.com")
    monkeypatch.setattr(settings, "sunsynk_password", "secret")
    monkeypatch.setattr(settings, "sunsynk_plant_id", "537603")
    monkeypatch.setattr(settings, "sunsynk_inverter_sn", SN)
    monkeypatch.setattr(settings, "enable_live_writes", False)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", False)


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/anonymous/publicKey":
        return httpx.Response(200, json={"success": True, "data": TEST_PUBLIC_KEY_PEM})
    if path == "/oauth/token/new":
        return httpx.Response(200, json=MOCKS["token"])
    if path == READ_PATH:
        return httpx.Response(200, json=MOCKS["settings_read"])
    if path == WRITE_PATH and request.method == "POST":
        body = json.loads(request.content.decode())
        assert body["solarMaxSellPower"] == "2500"
        return httpx.Response(200, json=MOCKS["settings_write"])
    return httpx.Response(404, json={"success": False})


@pytest.mark.asyncio
async def test_export_limit_reads_then_writes_full_settings_when_flags_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "enable_live_writes", True)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", True)
    client = httpx.AsyncClient(
        base_url="https://api.test",
        transport=httpx.MockTransport(_handler),
        timeout=5.0,
    )
    adapter = SunsynkConnectAdapter(client=client)
    result = await adapter.set_export_limit(ExportLimitRequest(limit_w=2500))
    assert result["export_limit_w"] == 2500
    assert result["verified"] is False
    assert result["inverter_sn"] == SN


@pytest.mark.asyncio
async def test_export_limit_blocked_without_flags() -> None:
    client = httpx.AsyncClient(
        base_url="https://api.test",
        transport=httpx.MockTransport(_handler),
        timeout=5.0,
    )
    adapter = SunsynkConnectAdapter(client=client)
    with pytest.raises(UnsupportedWriteError):
        await adapter.set_export_limit(ExportLimitRequest(limit_w=2500))
