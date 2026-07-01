"""Tests for the Sunsynk Connect cloud adapter.

The Sunsynk Connect / Connect Pro HTTP API is community-inferred and UNVERIFIED.
These tests pin the adapter's behaviour against a fully mocked transport so we never
call the real cloud service, and so unverified write paths stay feature-flagged.
"""

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timezone

from app.adapters.sunsynk_connect import SunsynkConnectAdapter
from app.config import settings
from app.schemas.domain import (
    AdapterError,
    BatteryControlRequest,
    ExportLimitRequest,
    ForceBatteryAction,
    ForceBatteryRequest,
    HouseLoadSource,
    TouBandsRequest,
    TouBandWrite,
    UnsupportedWriteError,
)

TOKEN_RESPONSE = {"success": True, "data": {"access_token": "tok-123", "expires_in": 3600}}
FLOW_RESPONSE = {
    "success": True,
    "data": {
        "pvPower": 4200,
        "soc": 68,
        "loadOrEpsPower": 1800,
        "gridOrMeterPower": -2400,
        "battPower": 600,
        "etodayPv": 14.2,
        "etodayFrom": 1.5,
        "etodayTo": 6.1,
    },
}

_TEST_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_PUBLIC_KEY_PEM = (
    _TEST_PRIVATE_KEY.public_key()
    .public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode("utf-8")
)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="https://api.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
    )


@pytest.fixture(autouse=True)
def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sunsynk_username", "user@example.com")
    monkeypatch.setattr(settings, "sunsynk_password", "secret")
    monkeypatch.setattr(settings, "sunsynk_plant_id", "123")
    monkeypatch.setattr(settings, "sunsynk_inverter_sn", "INV123")
    monkeypatch.setattr(settings, "enable_live_writes", False)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", False)


def _ok_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/anonymous/publicKey":
        return httpx.Response(200, json={"success": True, "data": TEST_PUBLIC_KEY_PEM})
    if path == "/oauth/token/new":
        body = request.read().decode()
        assert "secret" not in body
        return httpx.Response(200, json=TOKEN_RESPONSE)
    if path.endswith("/flow"):
        assert request.headers.get("Authorization") == "Bearer tok-123"
        return httpx.Response(200, json=FLOW_RESPONSE)
    if path == "/api/v1/common/setting/INV123/read":
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {"sn": "INV123", "solarMaxSellPower": "3000", "sysWorkMode": "2"},
            },
        )
    if request.method == "POST" and path == "/api/v1/common/setting/INV123/set":
        return httpx.Response(200, json={"success": True, "data": {"exportLimit": 3000}})
    return httpx.Response(404, json={"success": False})


LOW_LOAD_FLOW_RESPONSE = {
    "success": True,
    "data": {
        "pvPower": 9,
        "soc": 95,
        "loadOrEpsPower": 0,
        "homeLoadPower": 0,
        "gridOrMeterPower": 12,
        "gridTo": True,
        "toGrid": False,
        "battPower": 1,
        "batTo": True,
    },
}

def _low_load_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/anonymous/publicKey":
        return httpx.Response(200, json={"success": True, "data": TEST_PUBLIC_KEY_PEM})
    if path == "/oauth/token/new":
        return httpx.Response(200, json=TOKEN_RESPONSE)
    if path.endswith("/flow"):
        return httpx.Response(200, json=LOW_LOAD_FLOW_RESPONSE)
    if "/plant/energy/" in path and path.endswith("/day"):
        return httpx.Response(200, json=DAY_SERIES_RESPONSE)
    if path == "/api/v1/plants":
        return httpx.Response(200, json={"success": True, "data": [{"id": "123"}]})
    return httpx.Response(404, json={"success": False})


def test_flow_daily_totals_parses_etoday_fields() -> None:
    totals = SunsynkConnectAdapter._flow_daily_totals(
        {
            "etodayPv": 14.2,
            "etodayFrom": 1.5,
            "etodayTo": 6.1,
        }
    )
    assert totals == {"pv": 14.2, "import": 1.5, "export": 6.1}


@pytest.mark.asyncio
async def test_capabilities_read_ready_writes_gated() -> None:
    adapter = SunsynkConnectAdapter(client=_client(_ok_handler))
    caps = await adapter.get_capabilities()
    assert caps.mode == "sunsynk_connect"
    assert caps.supports_read is True
    assert caps.supports_write is False
    assert caps.supported_writes == []
    assert caps.notes


@pytest.mark.asyncio
async def test_get_live_metrics_parses_flow() -> None:
    adapter = SunsynkConnectAdapter(client=_client(_ok_handler))
    metrics = await adapter.get_live_metrics()
    assert metrics.pv_power_w == 4200
    assert metrics.battery_soc_pct == 68
    assert metrics.house_load_w == 2400
    assert metrics.house_load_source == HouseLoadSource.DERIVED
    assert metrics.grid_export_w == 2400
    assert metrics.grid_import_w == 0
    assert metrics.battery_power_w == 600
    assert metrics.daily_pv_kwh == pytest.approx(14.2)
    assert metrics.daily_import_kwh == pytest.approx(1.5)
    assert metrics.daily_export_kwh == pytest.approx(6.1)


@pytest.mark.asyncio
async def test_get_live_metrics_low_load_matches_sunsynk_and_fills_daily_kwh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live watts match Sunsynk /flow; day-series fills kWh when etoday* absent."""
    adapter = SunsynkConnectAdapter(client=_client(_low_load_handler))

    async def fake_daily(_plant_id: str):
        return (
            {"pv": 0.679, "import": 30.825, "export": 0.375},
            296.0,
            datetime(2026, 7, 1, 5, 25, tzinfo=timezone.utc),
        )

    monkeypatch.setattr(adapter, "_daily_day_data", fake_daily)
    metrics = await adapter.get_live_metrics()
    assert metrics.pv_power_w == pytest.approx(9)
    assert metrics.grid_import_w == pytest.approx(12)
    assert metrics.house_load_w == pytest.approx(22)
    assert metrics.house_load_source == HouseLoadSource.DERIVED
    assert metrics.daily_pv_kwh == pytest.approx(0.679)
    assert metrics.daily_import_kwh == pytest.approx(30.825)
    assert metrics.daily_export_kwh == pytest.approx(0.375)


@pytest.mark.asyncio
async def test_concurrent_requests_share_single_login() -> None:
    import asyncio

    token_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls
        if request.url.path == "/oauth/token/new":
            token_calls += 1
        return _ok_handler(request)

    adapter = SunsynkConnectAdapter(client=_client(handler))
    await asyncio.gather(*(adapter.get_live_metrics() for _ in range(8)))
    # Without the auth lock + token cache, each concurrent call would log in,
    # invalidating the others' tokens (Sunsynk allows one token per account).
    assert token_calls == 1


@pytest.mark.asyncio
async def test_cached_token_is_reused_across_calls() -> None:
    token_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls
        if request.url.path == "/oauth/token/new":
            token_calls += 1
        return _ok_handler(request)

    adapter = SunsynkConnectAdapter(client=_client(handler))
    await adapter.get_live_metrics()
    await adapter.get_live_metrics()
    assert token_calls == 1


@pytest.mark.asyncio
async def test_connectivity_degraded_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sunsynk_username", "")
    monkeypatch.setattr(settings, "sunsynk_password", "")
    adapter = SunsynkConnectAdapter(client=_client(_ok_handler))
    status = await adapter.get_connectivity()
    assert status.adapter_connected is False
    assert status.degraded_reason


@pytest.mark.asyncio
async def test_timeout_raises_adapter_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    adapter = SunsynkConnectAdapter(client=_client(handler))
    with pytest.raises(AdapterError):
        await adapter.get_live_metrics()


@pytest.mark.asyncio
async def test_export_limit_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = SunsynkConnectAdapter(client=_client(_ok_handler))
    with pytest.raises(UnsupportedWriteError):
        await adapter.set_export_limit(ExportLimitRequest(limit_w=3000))


@pytest.mark.asyncio
async def test_export_limit_blocked_when_only_master_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "enable_live_writes", True)
    adapter = SunsynkConnectAdapter(client=_client(_ok_handler))
    with pytest.raises(UnsupportedWriteError):
        await adapter.set_export_limit(ExportLimitRequest(limit_w=3000))


@pytest.mark.asyncio
async def test_export_limit_attempts_when_flags_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "enable_live_writes", True)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", True)
    adapter = SunsynkConnectAdapter(client=_client(_ok_handler))
    result = await adapter.set_export_limit(ExportLimitRequest(limit_w=3000))
    assert result["export_limit_w"] == 3000
    assert result["verified"] is False


@pytest.mark.asyncio
async def test_capabilities_lists_tou_when_writes_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "enable_live_writes", True)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", True)
    adapter = SunsynkConnectAdapter(client=_client(_ok_handler))
    caps = await adapter.get_capabilities()
    assert caps.supports_write is True
    assert "tou" in caps.supported_writes
    assert "force_battery" in caps.supported_writes


@pytest.mark.asyncio
async def test_set_tou_bands_writes_both_grid_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/set"):
            captured.update(__import__("json").loads(request.content.decode()))
            return httpx.Response(200, json={"success": True, "data": {}})
        return _ok_handler(request)

    monkeypatch.setattr(settings, "enable_live_writes", True)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", True)
    adapter = SunsynkConnectAdapter(client=_client(handler))
    result = await adapter.set_tou_bands(
        TouBandsRequest(
            bands=[
                TouBandWrite(
                    slot=1,
                    start="00:30",
                    target_soc_pct=80,
                    grid_charge_enabled=True,
                    power_w=3000,
                )
            ]
        )
    )
    assert result["bands"] == 1
    assert captured["sellTime1"] == "00:30"
    assert captured["cap1"] == "80"
    assert captured["time1on"] == "true"
    assert captured["time1On"] == "1"
    assert captured["sellTime1Pac"] == "3000"


@pytest.mark.asyncio
async def test_set_tou_bands_blocked_without_flags() -> None:
    adapter = SunsynkConnectAdapter(client=_client(_ok_handler))
    with pytest.raises(UnsupportedWriteError):
        await adapter.set_tou_bands(
            TouBandsRequest(bands=[TouBandWrite(slot=1, start="00:00")])
        )


@pytest.mark.asyncio
async def test_set_battery_control_writes_currents(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/set"):
            captured.update(__import__("json").loads(request.content.decode()))
            return httpx.Response(200, json={"success": True, "data": {}})
        return _ok_handler(request)

    monkeypatch.setattr(settings, "enable_live_writes", True)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", True)
    adapter = SunsynkConnectAdapter(client=_client(handler))
    result = await adapter.set_battery_control(
        BatteryControlRequest(charge_current_a=120, discharge_current_a=140)
    )
    assert captured["chargeCurrent"] == "120"
    assert captured["dischargeCurrent"] == "140"
    assert result["charge_current_a"] == 120


@pytest.mark.asyncio
async def test_force_battery_charge_edits_active_band(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/set"):
            captured.update(__import__("json").loads(request.content.decode()))
            return httpx.Response(200, json={"success": True, "data": {}})
        return _ok_handler(request)

    monkeypatch.setattr(settings, "enable_live_writes", True)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", True)
    adapter = SunsynkConnectAdapter(client=_client(handler))
    result = await adapter.force_battery(ForceBatteryRequest(action=ForceBatteryAction.CHARGE))
    slot = result["active_slot"]
    assert captured[f"time{slot}on"] == "true"
    assert captured[f"cap{slot}"] == "100"


@pytest.mark.asyncio
async def test_force_battery_discharge_drops_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/set"):
            captured.update(__import__("json").loads(request.content.decode()))
            return httpx.Response(200, json={"success": True, "data": {}})
        return _ok_handler(request)

    monkeypatch.setattr(settings, "enable_live_writes", True)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", True)
    adapter = SunsynkConnectAdapter(client=_client(handler))
    result = await adapter.force_battery(ForceBatteryRequest(action=ForceBatteryAction.DISCHARGE))
    slot = result["active_slot"]
    assert captured[f"time{slot}on"] == "false"
    assert captured[f"time{slot}On"] == "0"


@pytest.mark.asyncio
async def test_force_battery_stop_disables_grid_charge(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/set"):
            captured.update(__import__("json").loads(request.content.decode()))
            return httpx.Response(200, json={"success": True, "data": {}})
        return _ok_handler(request)

    monkeypatch.setattr(settings, "enable_live_writes", True)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", True)
    adapter = SunsynkConnectAdapter(client=_client(handler))
    result = await adapter.force_battery(ForceBatteryRequest(action=ForceBatteryAction.STOP))
    slot = result["active_slot"]
    assert captured[f"time{slot}on"] == "false"


@pytest.mark.asyncio
async def test_set_battery_control_does_not_apply_grid_charge_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/set"):
            captured.update(__import__("json").loads(request.content.decode()))
            return httpx.Response(200, json={"success": True, "data": {}})
        return _ok_handler(request)

    monkeypatch.setattr(settings, "enable_live_writes", True)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", True)
    adapter = SunsynkConnectAdapter(client=_client(handler))
    result = await adapter.set_battery_control(
        BatteryControlRequest(grid_charge_current_a=30)
    )
    assert result["grid_charge_current_a_applied"] is False
    assert "gridChargeCurrent" not in captured


@pytest.mark.asyncio
async def test_request_refreshes_token_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stale token (401) should trigger one re-auth + retry, then succeed."""
    state = {"set_calls": 0, "token_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/oauth/token/new":
            state["token_calls"] += 1
            return httpx.Response(200, json=TOKEN_RESPONSE)
        if request.method == "POST" and path.endswith("/set"):
            state["set_calls"] += 1
            if state["set_calls"] == 1:
                return httpx.Response(401, json={"success": False, "msg": "token expired"})
            return httpx.Response(200, json={"success": True, "data": {"exportLimit": 3000}})
        return _ok_handler(request)

    monkeypatch.setattr(settings, "enable_live_writes", True)
    monkeypatch.setattr(settings, "sunsynk_enable_unverified_writes", True)
    adapter = SunsynkConnectAdapter(client=_client(handler))
    result = await adapter.set_export_limit(ExportLimitRequest(limit_w=3000))
    assert result["export_limit_w"] == 3000
    assert state["set_calls"] == 2
    assert state["token_calls"] >= 1
