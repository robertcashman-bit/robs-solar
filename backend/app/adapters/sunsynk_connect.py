"""Sunsynk Connect / Connect Pro cloud adapter.

This is the primary live integration path for accounts that already use the
Sunsynk Connect web/app service (no Home Assistant required).

IMPORTANT SAFETY / HONESTY NOTES:
- The Sunsynk Connect HTTP API is NOT officially documented for third parties.
  The endpoints and payload shapes used here are COMMUNITY-INFERRED and UNVERIFIED.
- All read parsing is defensive and tolerant of missing fields.
- All write paths are UNVERIFIED and gated behind two feature flags
  (ENABLE_LIVE_WRITES and SUNSYNK_ENABLE_UNVERIFIED_WRITES). They are disabled by
  default and, when enabled, return results explicitly marked ``verified=False``.
- Secrets (username/password/token) live only on the backend and are never logged.
"""

import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.adapters.base import InverterAdapter
from app.adapters.sunsynk_auth import login as sunsynk_login
from app.adapters.sunsynk_tou import (
    active_band_index,
    diagnose_battery_hold,
    parse_tou_bands,
    permissions_allow_write,
    work_mode_label,
)
from app.config import settings
from app.schemas.domain import (
    AdapterCapabilities,
    AdapterError,
    BatteryControlRequest,
    ConnectivityStatus,
    ExportLimitRequest,
    ForceBatteryAction,
    ForceBatteryRequest,
    InverterMode,
    InverterSettingsResponse,
    InverterStatus,
    LiveMetrics,
    OperatingModeRequest,
    ScheduleRequest,
    TouBandsRequest,
    UnsupportedWriteError,
)

_PLANTS_PATH = "/api/v1/plants"
_MODE = "sunsynk_connect"
# The Sunsynk /flow endpoint has no daily energy totals, so they are derived by
# integrating the 5-minute day series. That series only updates every 5 minutes,
# so we cache the computed totals to avoid an extra call on every live poll.
_DAILY_TOTALS_TTL_SECONDS = 300.0


class SunsynkConnectAdapter(InverterAdapter):
    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        base_url = settings.sunsynk_base_url.rstrip("/") if settings.sunsynk_base_url else None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=settings.sunsynk_timeout_seconds,
        )
        self._token: Optional[str] = None
        # (monotonic_expiry, local_date, totals) cache for derived daily energy.
        self._daily_cache: Optional[tuple[float, str, dict[str, float]]] = None

    async def _request(
        self, method: str, url: str, *, _auth_retry: bool = True, **kwargs: Any
    ) -> httpx.Response:
        attempts = max(1, settings.sunsynk_max_retries + 1)
        last_exc: Optional[Exception] = None
        for _ in range(attempts):
            try:
                response = await self._client.request(method, url, **kwargs)
                # Sunsynk issues a single active token per account, so a concurrent
                # login (e.g. the live-metrics poller) can invalidate ours mid-request.
                # Refresh the token once and retry before surfacing the error.
                if response.status_code == 401 and _auth_retry:
                    self._token = None
                    self._client.headers.pop("Authorization", None)
                    await self._authenticate()
                    return await self._request(method, url, _auth_retry=False, **kwargs)
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                last_exc = exc
                continue
            except httpx.HTTPError as exc:
                raise AdapterError(f"Sunsynk request failed: {exc}") from exc
        raise AdapterError(
            f"Sunsynk request timed out after {attempts} attempt(s)"
        ) from last_exc

    async def _authenticate(self) -> str:
        if not settings.sunsynk_username or not settings.sunsynk_password:
            raise AdapterError("Sunsynk credentials not configured")
        if self._token:
            return self._token
        try:
            data = await sunsynk_login(
                self._client,
                username=settings.sunsynk_username,
                plain_password=settings.sunsynk_password,
            )
        except (httpx.HTTPError, ValueError) as exc:
            raise AdapterError(f"Sunsynk authentication failed: {exc}") from exc
        token = data.get("access_token")
        if not token:
            raise AdapterError("Sunsynk authentication returned no access token")
        self._token = token
        self._client.headers["Authorization"] = f"Bearer {token}"
        return token

    async def _plant_id(self) -> str:
        if settings.sunsynk_plant_id:
            return settings.sunsynk_plant_id
        response = await self._request(
            "GET",
            _PLANTS_PATH,
            params={"page": 1, "limit": 10, "status": -1},
        )
        data = response.json().get("data") or {}
        infos = data.get("infos") or []
        if not infos:
            raise AdapterError("No Sunsynk plants found for this account")
        return str(infos[0].get("id"))

    async def _inverter_sn(self) -> str:
        if settings.sunsynk_inverter_sn:
            return settings.sunsynk_inverter_sn
        await self._authenticate()
        plant_id = await self._plant_id()
        response = await self._request(
            "GET",
            f"/api/v1/plant/{plant_id}/inverters",
            params={"page": 1, "limit": 10, "type": 2, "status": 1},
        )
        infos = (response.json().get("data") or {}).get("infos") or []
        if not infos:
            raise AdapterError("No inverters found for Sunsynk plant")
        sn = infos[0].get("sn")
        if not sn:
            raise AdapterError("Sunsynk inverter list missing serial number")
        return str(sn)

    async def _plant_detail(self) -> dict[str, Any]:
        plant_id = await self._plant_id()
        response = await self._request("GET", f"/api/v1/plant/{plant_id}", params={"lan": "en"})
        return response.json().get("data") or {}

    async def _read_settings_raw(self, inverter_sn: str) -> dict[str, Any]:
        response = await self._request("GET", f"/api/v1/common/setting/{inverter_sn}/read")
        body = response.json()
        if not body.get("success"):
            raise AdapterError(body.get("msg") or "Failed to read Sunsynk settings")
        data = body.get("data")
        if not isinstance(data, dict):
            raise AdapterError("Sunsynk settings read returned no data")
        return data

    async def _write_settings_raw(
        self, inverter_sn: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/api/v1/common/setting/{inverter_sn}/set",
            json=payload,
        )
        body = response.json()
        if not body.get("success"):
            msg = body.get("msg") or "Sunsynk settings write failed"
            raise AdapterError(msg)
        return body

    async def get_capabilities(self) -> AdapterCapabilities:
        read_ready = bool(settings.sunsynk_username and settings.sunsynk_password)
        write_ready = bool(
            settings.enable_live_writes and settings.sunsynk_enable_unverified_writes
        )
        writes = (
            [
                "export_limit",
                "schedule",
                "tou",
                "operating_mode",
                "battery",
                "force_battery",
            ]
            if write_ready
            else []
        )
        return AdapterCapabilities(
            mode=_MODE,
            supports_read=read_ready,
            supports_write=write_ready,
            supported_writes=writes,
            notes=[
                "Sunsynk Connect / Connect Pro cloud adapter.",
                "Writes use a read-modify-write on the inverter settings document.",
                "Live writes require ENABLE_LIVE_WRITES and "
                "SUNSYNK_ENABLE_UNVERIFIED_WRITES on the backend.",
            ],
        )

    def _parse_flow(self, payload: dict[str, Any]) -> LiveMetrics:
        data = payload.get("data") or {}

        def num(key: str) -> float:
            value = data.get(key, 0)
            try:
                return float(value if value is not None else 0)
            except (TypeError, ValueError) as exc:
                raise AdapterError(f"Malformed Sunsynk flow field '{key}'") from exc

        grid = num("gridOrMeterPower")
        fault_raw = data.get("fault") or data.get("faultCode") or data.get("alarm")
        has_fault = bool(fault_raw) and str(fault_raw) not in ("0", "none", "None", "")
        soh_raw = data.get("soh") or data.get("batterySoh") or data.get("battSoh")
        soh: float | None = None
        if soh_raw is not None:
            try:
                soh = float(soh_raw)
            except (TypeError, ValueError):
                soh = None
        return LiveMetrics(
            pv_power_w=max(0.0, num("pvPower")),
            battery_soc_pct=min(100.0, max(0.0, num("soc"))),
            battery_power_w=num("battPower"),
            house_load_w=max(0.0, num("loadOrEpsPower")),
            grid_import_w=grid if grid > 0 else 0.0,
            grid_export_w=-grid if grid < 0 else 0.0,
            inverter_mode=InverterMode.SELF_USE,
            inverter_status=InverterStatus.FAULT if has_fault else InverterStatus.ONLINE,
            battery_soh_pct=soh,
            # The /flow endpoint carries no daily energy totals; they are filled in
            # by get_live_metrics() from the daily series. Start at zero.
            daily_pv_kwh=0.0,
            daily_import_kwh=0.0,
            daily_export_kwh=0.0,
            timestamp=datetime.now(timezone.utc),
        )

    @staticmethod
    def _integrate_day_series(infos: list[dict[str, Any]]) -> dict[str, float]:
        """Integrate the 5-minute day series into kWh totals.

        The Sunsynk day endpoint returns labelled power series (PV, Grid, Load,
        ...) at a fixed cadence. Grid is signed: positive = import, negative =
        export. We sum each step as power(W) * step(h) / 1000 -> kWh.
        """
        by_label: dict[str, list[dict[str, Any]]] = {
            str(s.get("label") or ""): (s.get("records") or []) for s in infos
        }

        def _minutes(value: Any) -> Optional[int]:
            try:
                hh, mm = str(value).split(":")
                return int(hh) * 60 + int(mm)
            except (TypeError, ValueError):
                return None

        def step_hours(records: list[dict[str, Any]]) -> float:
            # The series is a partial-day feed at a fixed cadence (e.g. 5 min), so
            # derive the step from consecutive timestamps rather than the count.
            # Fall back to 5 minutes if timestamps are unusable.
            for first, second in zip(records, records[1:]):
                a, b = _minutes(first.get("time")), _minutes(second.get("time"))
                if a is not None and b is not None and b > a:
                    return (b - a) / 60.0
            return 5.0 / 60.0

        def integrate(label: str, *, positive_only: bool, invert: bool) -> float:
            records = by_label.get(label, [])
            hours = step_hours(records)
            total_wh = 0.0
            for record in records:
                try:
                    value = float(record.get("value"))
                except (TypeError, ValueError):
                    continue
                if invert:
                    value = -value
                if positive_only and value <= 0:
                    continue
                total_wh += value * hours
            return round(total_wh / 1000.0, 3)

        return {
            "pv": integrate("PV", positive_only=True, invert=False),
            "import": integrate("Grid", positive_only=True, invert=False),
            "export": integrate("Grid", positive_only=True, invert=True),
        }

    async def _daily_totals(self, plant_id: str) -> dict[str, float]:
        local_date = datetime.now().strftime("%Y-%m-%d")
        now = time.monotonic()
        if self._daily_cache is not None:
            expiry, cached_date, totals = self._daily_cache
            if cached_date == local_date and now < expiry:
                return totals
        response = await self._request(
            "GET",
            f"/api/v1/plant/energy/{plant_id}/day",
            params={"date": local_date, "id": plant_id, "lan": "en"},
        )
        data = response.json().get("data") or {}
        totals = self._integrate_day_series(data.get("infos") or [])
        self._daily_cache = (now + _DAILY_TOTALS_TTL_SECONDS, local_date, totals)
        return totals

    async def get_live_metrics(self) -> LiveMetrics:
        await self._authenticate()
        plant_id = await self._plant_id()
        response = await self._request("GET", f"/api/v1/plant/energy/{plant_id}/flow")
        metrics = self._parse_flow(response.json())
        try:
            totals = await self._daily_totals(plant_id)
            metrics.daily_pv_kwh = totals["pv"]
            metrics.daily_import_kwh = totals["import"]
            metrics.daily_export_kwh = totals["export"]
        except (AdapterError, httpx.HTTPError, KeyError, ValueError):
            # Daily totals are best-effort; never fail the live read over them.
            pass
        return metrics

    async def get_connectivity(self) -> ConnectivityStatus:
        if not settings.sunsynk_username or not settings.sunsynk_password:
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode=_MODE,
                adapter_connected=False,
                degraded_reason="Sunsynk credentials not configured",
            )
        try:
            await self._authenticate()
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode=_MODE,
                adapter_connected=True,
                last_successful_poll=datetime.now(timezone.utc),
            )
        except AdapterError as exc:
            return ConnectivityStatus(
                backend_healthy=True,
                adapter_mode=_MODE,
                adapter_connected=False,
                degraded_reason=str(exc),
            )

    def _ensure_writes_enabled(self, name: str) -> None:
        if not settings.enable_live_writes:
            raise UnsupportedWriteError(
                "Live writes are disabled. Set ENABLE_LIVE_WRITES=true to allow."
            )
        if not settings.sunsynk_enable_unverified_writes:
            raise UnsupportedWriteError(
                f"Sunsynk '{name}' write is UNVERIFIED and disabled. "
                "Set SUNSYNK_ENABLE_UNVERIFIED_WRITES=true to attempt at your own risk."
            )

    async def get_inverter_settings(self) -> Optional[InverterSettingsResponse]:
        await self._authenticate()
        plant = await self._plant_detail()
        inverter_sn = await self._inverter_sn()
        raw = await self._read_settings_raw(inverter_sn)
        bands = parse_tou_bands(raw)
        active_slot = active_band_index(bands)
        active = next((b for b in bands if b.slot == active_slot), None) if active_slot else None
        permissions = list(plant.get("plantPermission") or [])
        write_allowed = permissions_allow_write(permissions)
        write_denied = ""
        if not write_allowed:
            master = plant.get("master") or {}
            nickname = master.get("nickname") or "the plant owner"
            write_denied = (
                f"Sunsynk account has view-only access. Ask {nickname} or your installer "
                "for full control permission."
            )
        discharge = raw.get("dischargeCurrent")
        try:
            discharge_a = int(float(discharge)) if discharge not in (None, "") else None
        except (TypeError, ValueError):
            discharge_a = None
        return InverterSettingsResponse(
            inverter_sn=inverter_sn,
            plant_id=str(plant.get("id") or settings.sunsynk_plant_id or ""),
            plant_name=str(plant.get("name") or ""),
            plant_permissions=permissions,
            write_allowed=write_allowed,
            write_denied_reason=write_denied,
            sys_work_mode=str(raw.get("sysWorkMode") or ""),
            sys_work_mode_label=work_mode_label(str(raw.get("sysWorkMode") or "")),
            energy_mode=str(raw.get("energyMode") or ""),
            solar_sell=str(raw.get("solarSell") or "").lower() in {"1", "true"},
            export_limit_mode=str(raw.get("limit") or ""),
            discharge_current_a=discharge_a,
            bands=bands,
            active_band_slot=active_slot,
            active_band=active,
            diagnosis=diagnose_battery_hold(bands, active_slot),
        )

    async def set_export_limit(self, request: ExportLimitRequest) -> dict[str, Any]:
        self._ensure_writes_enabled("export_limit")
        inverter_sn = await self._inverter_sn()
        settings_data = await self._read_settings_raw(inverter_sn)
        settings_data["solarMaxSellPower"] = str(request.limit_w)
        body = await self._write_settings_raw(inverter_sn, settings_data)
        return {
            "export_limit_w": request.limit_w,
            "inverter_sn": inverter_sn,
            "verified": False,
            "raw": body,
        }

    @staticmethod
    def _set_grid_charge(data: dict[str, Any], slot: int, enabled: bool) -> None:
        """Sunsynk stores the grid-charge flag in two parallel fields per band."""
        data[f"time{slot}on"] = "true" if enabled else "false"
        data[f"time{slot}On"] = "1" if enabled else "0"

    async def set_schedule(self, request: ScheduleRequest) -> dict[str, Any]:
        self._ensure_writes_enabled("schedule")
        inverter_sn = await self._inverter_sn()
        settings_data = await self._read_settings_raw(inverter_sn)
        for idx, window in enumerate(request.windows[:6], start=1):
            settings_data[f"sellTime{idx}"] = window.start
            if window.target_soc_pct is not None:
                settings_data[f"cap{idx}"] = str(window.target_soc_pct)
            if window.grid_charge_enabled is not None:
                self._set_grid_charge(settings_data, idx, window.grid_charge_enabled)
            if window.power_w is not None:
                settings_data[f"sellTime{idx}Pac"] = str(window.power_w)
        body = await self._write_settings_raw(inverter_sn, settings_data)
        return {
            "inverter_sn": inverter_sn,
            "verified": False,
            "windows": len(request.windows),
            "raw": body,
        }

    async def set_tou_bands(self, request: TouBandsRequest) -> dict[str, Any]:
        """Write the full six-band time-of-use schedule (read-modify-write)."""
        self._ensure_writes_enabled("tou")
        inverter_sn = await self._inverter_sn()
        settings_data = await self._read_settings_raw(inverter_sn)
        for band in request.bands:
            slot = band.slot
            settings_data[f"sellTime{slot}"] = band.start
            if band.target_soc_pct is not None:
                settings_data[f"cap{slot}"] = str(band.target_soc_pct)
            self._set_grid_charge(settings_data, slot, band.grid_charge_enabled)
            if band.power_w is not None:
                settings_data[f"sellTime{slot}Pac"] = str(band.power_w)
        body = await self._write_settings_raw(inverter_sn, settings_data)
        return {
            "inverter_sn": inverter_sn,
            "verified": False,
            "bands": len(request.bands),
            "raw": body,
        }

    async def set_operating_mode(self, request: OperatingModeRequest) -> dict[str, Any]:
        self._ensure_writes_enabled("operating_mode")
        mode_map = {
            InverterMode.FEED_IN: "2",
            InverterMode.BACKUP: "0",
            InverterMode.SELF_USE: "1",
            InverterMode.OFF_GRID: "1",
        }
        inverter_sn = await self._inverter_sn()
        settings_data = await self._read_settings_raw(inverter_sn)
        settings_data["sysWorkMode"] = mode_map.get(request.mode, "1")
        body = await self._write_settings_raw(inverter_sn, settings_data)
        return {
            "inverter_sn": inverter_sn,
            "operating_mode": request.mode.value,
            "verified": False,
            "raw": body,
        }

    async def set_battery_control(self, request: BatteryControlRequest) -> dict[str, Any]:
        self._ensure_writes_enabled("battery")
        inverter_sn = await self._inverter_sn()
        settings_data = await self._read_settings_raw(inverter_sn)
        if request.charge_current_a is not None:
            settings_data["chargeCurrent"] = str(request.charge_current_a)
        if request.discharge_current_a is not None:
            settings_data["dischargeCurrent"] = str(request.discharge_current_a)
        body = await self._write_settings_raw(inverter_sn, settings_data)
        return {
            "inverter_sn": inverter_sn,
            "verified": False,
            "charge_current_a": request.charge_current_a,
            "discharge_current_a": request.discharge_current_a,
            # No dedicated grid-charge current register is exposed by this API.
            "grid_charge_current_a_applied": False,
            "raw": body,
        }

    async def force_battery(self, request: ForceBatteryRequest) -> dict[str, Any]:
        """Force charge/discharge by editing the currently active TOU band."""
        self._ensure_writes_enabled("force_battery")
        inverter_sn = await self._inverter_sn()
        settings_data = await self._read_settings_raw(inverter_sn)
        bands = parse_tou_bands(settings_data)
        slot = active_band_index(bands) or 1
        if request.action == ForceBatteryAction.CHARGE:
            self._set_grid_charge(settings_data, slot, True)
            settings_data[f"cap{slot}"] = "100"
        elif request.action == ForceBatteryAction.DISCHARGE:
            low_cap = settings_data.get("batteryLowCap") or "20"
            self._set_grid_charge(settings_data, slot, False)
            settings_data[f"cap{slot}"] = str(low_cap)
        else:  # STOP
            self._set_grid_charge(settings_data, slot, False)
        body = await self._write_settings_raw(inverter_sn, settings_data)
        return {
            "inverter_sn": inverter_sn,
            "verified": False,
            "action": request.action.value,
            "active_slot": slot,
            "raw": body,
        }

    async def get_last_known_good(self) -> Optional[dict[str, Any]]:
        try:
            await self._authenticate()
            inverter_sn = await self._inverter_sn()
            return await self._read_settings_raw(inverter_sn)
        except AdapterError:
            return None
