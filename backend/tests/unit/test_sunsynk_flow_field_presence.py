"""Raw /flow payload capture and missing-vs-zero field presence auditing.

Covers task requirements: log the raw payload before transformation, and
report missing/undefined load fields as "unknown" rather than silently
treating them the same as a genuine 0 reading.
"""

from __future__ import annotations

import httpx
import pytest

from app.adapters.sunsynk_connect import SunsynkConnectAdapter
from app.config import settings
from app.schemas.domain import HouseLoadSource, LoadFieldOrigin


@pytest.fixture(autouse=True)
def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sunsynk_username", "user@example.com")
    monkeypatch.setattr(settings, "sunsynk_password", "secret")
    monkeypatch.setattr(settings, "sunsynk_plant_id", "123")
    monkeypatch.setattr(settings, "sunsynk_inverter_sn", "INV123")


def _adapter() -> SunsynkConnectAdapter:
    return SunsynkConnectAdapter(client=httpx.AsyncClient(base_url="https://api.test"))


def test_no_diagnostics_before_first_flow_fetch() -> None:
    adapter = _adapter()
    assert adapter.get_load_diagnostics() is None


def test_field_present_and_zero_is_not_confused_with_missing() -> None:
    """loadOrEpsPower/homeLoadPower are present (0); upsLoadPower is absent."""
    adapter = _adapter()
    adapter._parse_flow(
        {
            "data": {
                "pvPower": 9,
                "soc": 95,
                "loadOrEpsPower": 0,
                "homeLoadPower": 0,
                "gridOrMeterPower": 12,
                "battPower": 1,
                "existsMeter": False,
                # upsLoadPower intentionally absent from the payload
            }
        }
    )
    diagnostics = adapter.get_load_diagnostics()
    assert diagnostics is not None
    presence = diagnostics["field_presence"]
    assert presence["loadOrEpsPower"] is True
    assert presence["homeLoadPower"] is True
    assert presence["upsLoadPower"] is False  # genuinely absent, not just 0
    raw_values = diagnostics["field_raw_values"]
    assert raw_values["loadOrEpsPower"] == 0
    assert raw_values["upsLoadPower"] is None  # .get() default for an absent key
    assert diagnostics["raw_payload"]["pvPower"] == 9
    assert diagnostics["captured_at"] is not None


def test_all_load_fields_missing_entirely_still_derives_load() -> None:
    """None of the three load candidate keys are present at all (not 0 -- absent)."""
    adapter = _adapter()
    metrics = adapter._parse_flow(
        {
            "data": {
                "pvPower": 0,
                "soc": 95,
                "gridOrMeterPower": 500,
                "battPower": 0,
                "existsMeter": False,
                # loadOrEpsPower, homeLoadPower, upsLoadPower all absent
            }
        }
    )
    diagnostics = adapter.get_load_diagnostics()
    assert diagnostics is not None
    for key in ("loadOrEpsPower", "homeLoadPower", "upsLoadPower"):
        assert diagnostics["field_presence"][key] is False
    # Missing load keys must not silently equal "reported 0" -- house load
    # should still be derived from the power balance (grid import here).
    assert metrics.house_load_w == pytest.approx(500)
    assert metrics.house_load_source == HouseLoadSource.DERIVED
    assert metrics.house_load_reported_w == 0.0


def test_explicit_null_load_fields_parsed_as_zero_not_error() -> None:
    """Sunsynk sometimes sends explicit JSON null rather than omitting the key."""
    adapter = _adapter()
    metrics = adapter._parse_flow(
        {
            "data": {
                "pvPower": None,
                "soc": 50,
                "loadOrEpsPower": None,
                "homeLoadPower": None,
                "upsLoadPower": None,
                "gridOrMeterPower": 300,
                "battPower": None,
                "existsMeter": False,
            }
        }
    )
    diagnostics = adapter.get_load_diagnostics()
    assert diagnostics is not None
    # Present in the payload (key exists) but with an explicit null value.
    assert diagnostics["field_presence"]["loadOrEpsPower"] is True
    assert diagnostics["field_raw_values"]["loadOrEpsPower"] is None
    assert metrics.pv_power_w == 0.0
    assert metrics.house_load_reported_w == 0.0
    assert metrics.house_load_w == pytest.approx(300)
    assert metrics.house_load_source == HouseLoadSource.DERIVED


def test_missing_load_field_warning_logged_once(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    adapter = _adapter()
    caplog.set_level(logging.WARNING, logger="app.adapters.sunsynk_connect")
    payload = {
        "data": {
            "pvPower": 0,
            "gridOrMeterPower": 0,
            "battPower": 0,
            "existsMeter": False,
        }
    }
    adapter._parse_flow(payload)
    adapter._parse_flow(payload)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "missing load field" in warnings[0].message.lower()


def test_missing_load_field_warning_resets_when_fields_return() -> None:
    adapter = _adapter()
    adapter._parse_flow({"data": {"pvPower": 0, "gridOrMeterPower": 0, "battPower": 0}})
    assert adapter._warned_missing_load_fields is True
    adapter._parse_flow(
        {
            "data": {
                "pvPower": 0,
                "loadOrEpsPower": 1200,
                "homeLoadPower": 1200,
                "upsLoadPower": 0,
                "gridOrMeterPower": 1200,
            }
        }
    )
    assert adapter._warned_missing_load_fields is False


def test_get_load_diagnostics_reflects_most_recent_call() -> None:
    adapter = _adapter()
    adapter._parse_flow({"data": {"pvPower": 100, "gridOrMeterPower": 0, "loadOrEpsPower": 100}})
    first = adapter.get_load_diagnostics()
    assert first is not None
    assert first["raw_payload"]["pvPower"] == 100
    adapter._parse_flow({"data": {"pvPower": 200, "gridOrMeterPower": 0, "loadOrEpsPower": 200}})
    second = adapter.get_load_diagnostics()
    assert second is not None
    assert second["raw_payload"]["pvPower"] == 200
    assert second["captured_at"] >= first["captured_at"]


def test_load_field_origin_enum_has_expected_values() -> None:
    assert LoadFieldOrigin.LIVE == "live"
    assert LoadFieldOrigin.DERIVED == "derived"
    assert LoadFieldOrigin.CACHED == "cached"
    assert LoadFieldOrigin.MISSING == "missing"
    assert LoadFieldOrigin.UNKNOWN == "unknown"
