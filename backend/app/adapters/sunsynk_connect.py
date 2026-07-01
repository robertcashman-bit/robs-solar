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

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app.adapters.base import InverterAdapter
from app.adapters.sunsynk_auth import login as sunsynk_login
from app.adapters.sunsynk_tou import (
    active_band_index,
    diagnose_battery_hold,
    parse_tou_bands,
    permissions_allow_write,
    work_mode_from_sunsynk,
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
    HouseLoadSource,
    InverterMode,
    InverterSettingsResponse,
    InverterStatus,
    LiveMetrics,
    OperatingModeRequest,
    ScheduleRequest,
    TouBandsRequest,
    UnsupportedWriteError,
    work_mode_to_inverter_mode,
)
from app.services.effective_load import finalize_live_metrics
from app.services.effective_load import resolve_house_load as _resolve_house_load_shared
from app.services.tariff_clock import tariff_now, tariff_zone

_PLANTS_PATH = "/api/v1/plants"
_MODE = "sunsynk_connect"
# The Sunsynk /flow endpoint may include etoday* daily counters; day series fills gaps.
_DAILY_TOTALS_TTL_SECONDS = 300.0


class SunsynkConnectAdapter(InverterAdapter):
    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        base_url = settings.sunsynk_base_url.rstrip("/") if settings.sunsynk_base_url else None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=settings.sunsynk_timeout_seconds,
        )
        self._token: Optional[str] = None
        # Monotonic time after which the cached token is considered stale and is
        # proactively refreshed (Sunsynk tokens expire; refreshing ahead of a 401
        # avoids surfacing transient auth failures).
        self._token_expiry: float = 0.0
        # Serialises logins so concurrent callers (live poll, sampler, alert
        # evaluation, etc.) perform at most one login. Sunsynk issues a single
        # active token per account, so parallel logins would invalidate each
        # other and produce spurious "authentication failed" errors.
        self._auth_lock = asyncio.Lock()
        # (monotonic_expiry, local_date, totals, latest_load_w, latest_load_at)
        self._daily_cache: Optional[
            tuple[float, str, dict[str, float], float, Optional[datetime]]
        ] = None

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
                    self._token_expiry = 0.0
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

    def _token_valid(self) -> bool:
        return bool(self._token) and time.monotonic() < self._token_expiry

    async def _authenticate(self) -> str:
        if not settings.sunsynk_username or not settings.sunsynk_password:
            raise AdapterError("Sunsynk credentials not configured")
        if self._token_valid():
            return self._token  # type: ignore[return-value]
        async with self._auth_lock:
            # Re-check inside the lock: another coroutine may have logged in while
            # we waited, so we reuse its token instead of logging in again.
            if self._token_valid():
                return self._token  # type: ignore[return-value]
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
            try:
                expires_in = float(data.get("expires_in") or 0)
            except (TypeError, ValueError):
                expires_in = 0.0
            # Refresh a minute early; fall back to a short window if the API does
            # not report an expiry so we still cache rather than logging in per call.
            lifetime = expires_in - 60 if expires_in > 120 else 240.0
            self._token = token
            self._token_expiry = time.monotonic() + lifetime
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

    @staticmethod
    def _flag(data: dict[str, Any], *keys: str) -> Optional[bool]:
        """Read a Sunsynk flow direction flag if present (else None)."""
        for key in keys:
            if key in data and data[key] is not None:
                raw = data[key]
                if isinstance(raw, bool):
                    return raw
                return str(raw).strip().lower() in {"1", "true", "yes", "on"}
        return None

    _POWER_NOISE_FLOOR_W = 5.0

    @staticmethod
    def _derived_house_load(
        pv: float, grid_import: float, grid_export: float, battery_power_w: float
    ) -> float:
        """House load implied by instantaneous power balance (positive batt = discharging)."""
        return pv + grid_import - grid_export + battery_power_w

    def _resolve_battery_power(
        self,
        data: dict[str, Any],
        raw_batt: float,
        *,
        pv: float,
        grid_import: float,
        grid_export: float,
        reported_load: float,
    ) -> float:
        """Battery power in app convention: positive = discharging.

        Sunsynk firmware varies: direction booleans (``toBat`` / ``batTo``),
        signed ``battPower`` (negative = discharging on many inverters), or an
        unsigned positive magnitude. Prefer explicit flags when they agree with
        the reported sign; when they conflict (common at low load), infer from
        the power balance instead.
        """
        charging = self._flag(data, "toBat", "toBattery", "gridToBat")
        discharging = self._flag(data, "batTo", "batteryTo", "batteryOut", "batToLoad")
        abs_mag = abs(raw_batt)
        if abs_mag < 1:
            return 0.0

        # Trust direction flags only when they match the sign of ``battPower``.
        if charging is True and discharging is not True and raw_batt >= 0:
            return -abs_mag
        if discharging is True and charging is not True:
            return abs_mag

        candidates: list[float] = []
        if raw_batt < 0:
            candidates.extend([abs_mag, -abs_mag])
        else:
            candidates.extend([abs_mag, -abs_mag])

        floor = self._POWER_NOISE_FLOOR_W

        def score(candidate: float) -> tuple[float, float]:
            derived = self._derived_house_load(pv, grid_import, grid_export, candidate)
            if reported_load > floor:
                return (0.0 if derived > floor else 1.0, abs(derived - reported_load))
            return (0.0 if derived > floor else 1.0, -derived)

        return min(candidates, key=score)

    @staticmethod
    def _resolve_house_load(
        reported: float,
        *,
        pv: float,
        grid_import: float,
        grid_export: float,
        battery_power_w: float,
    ) -> tuple[float, HouseLoadSource]:
        return _resolve_house_load_shared(
            reported,
            pv=pv,
            grid_import=grid_import,
            grid_export=grid_export,
            battery_power_w=battery_power_w,
        )

    def _signed_grid(self, data: dict[str, Any], grid: float) -> tuple[float, float]:
        """Return (import_w, export_w) using direction flags when present.

        Convention: positive ``gridOrMeterPower`` = importing. Flags ``gridTo``
        (importing) / ``toGrid`` (exporting) override the sign when the firmware
        reports an unsigned magnitude.
        """
        importing = self._flag(data, "gridTo", "gridToLoad", "gridToBat")
        exporting = self._flag(data, "toGrid", "pvToGrid")
        if importing is True and exporting is not True:
            return abs(grid), 0.0
        if exporting is True and importing is not True:
            return 0.0, abs(grid)
        return (grid if grid > 0 else 0.0, -grid if grid < 0 else 0.0)

    def _parse_flow(self, payload: dict[str, Any]) -> LiveMetrics:
        data = payload.get("data") or {}

        def num(key: str) -> float:
            value = data.get(key, 0)
            try:
                return float(value if value is not None else 0)
            except (TypeError, ValueError) as exc:
                raise AdapterError(f"Malformed Sunsynk flow field '{key}'") from exc

        pv_power_w = max(0.0, num("pvPower"))
        reported_load = max(
            num("loadOrEpsPower"),
            num("homeLoadPower"),
            num("upsLoadPower"),
        )
        grid = num("gridOrMeterPower")
        grid_import_w, grid_export_w = self._signed_grid(data, grid)
        battery_power_w = self._resolve_battery_power(
            data,
            num("battPower"),
            pv=pv_power_w,
            grid_import=grid_import_w,
            grid_export=grid_export_w,
            reported_load=reported_load,
        )
        house_load_w, house_load_source = self._resolve_house_load(
            reported_load,
            pv=pv_power_w,
            grid_import=grid_import_w,
            grid_export=grid_export_w,
            battery_power_w=battery_power_w,
        )
        fault_raw = data.get("fault") or data.get("faultCode") or data.get("alarm")
        has_fault = bool(fault_raw) and str(fault_raw) not in ("0", "none", "None", "")
        soh_raw = data.get("soh") or data.get("batterySoh") or data.get("battSoh")
        soh: float | None = None
        if soh_raw is not None:
            try:
                soh = float(soh_raw)
            except (TypeError, ValueError):
                soh = None
        work_mode_raw = data.get("sysWorkMode")
        work_mode = work_mode_from_sunsynk(work_mode_raw)
        flow_daily = self._flow_daily_totals(data)
        exists_meter = self._flag(data, "existsMeter")
        return LiveMetrics(
            pv_power_w=pv_power_w,
            battery_soc_pct=min(100.0, max(0.0, num("soc"))),
            battery_power_w=battery_power_w,
            house_load_w=house_load_w,
            house_load_source=house_load_source,
            house_load_reported_w=reported_load,
            grid_import_w=grid_import_w,
            grid_export_w=grid_export_w,
            inverter_mode=work_mode_to_inverter_mode(work_mode)
            if work_mode is not None
            else InverterMode.SELF_USE,
            inverter_status=InverterStatus.FAULT if has_fault else InverterStatus.ONLINE,
            battery_soh_pct=soh,
            system_work_mode=work_mode,
            daily_pv_kwh=flow_daily.get("pv", 0.0) if flow_daily else 0.0,
            daily_import_kwh=flow_daily.get("import", 0.0) if flow_daily else 0.0,
            daily_export_kwh=flow_daily.get("export", 0.0) if flow_daily else 0.0,
            timestamp=datetime.now(timezone.utc),
            grid_meter_connected=exists_meter,
        )

    @staticmethod
    def _flow_daily_totals(data: dict[str, Any]) -> Optional[dict[str, float]]:
        """Parse official Sunsynk daily counters from /flow (matches the mobile app)."""
        field_map = {
            "pv": ("etodayPv", "eTodayPv", "todayPv"),
            "import": ("etodayFrom", "eTodayFrom", "etodayImport", "todayImport"),
            "export": ("etodayTo", "eTodayTo", "etodayExport", "todayExport"),
        }
        totals: dict[str, float] = {}
        for label, keys in field_map.items():
            for key in keys:
                raw = data.get(key)
                if raw in (None, ""):
                    continue
                try:
                    totals[label] = max(0.0, float(raw))
                except (TypeError, ValueError):
                    continue
                break
        if "pv" not in totals:
            return None
        return {
            "pv": totals.get("pv", 0.0),
            "import": totals.get("import", 0.0),
            "export": totals.get("export", 0.0),
        }

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

    @staticmethod
    def _series_sample_time(local_date: str, time_value: Any) -> Optional[datetime]:
        try:
            hh, mm = str(time_value).split(":")
            hour, minute = int(hh), int(mm)
        except (TypeError, ValueError, AttributeError):
            return None
        try:
            year, month, day = (int(part) for part in local_date.split("-"))
        except (TypeError, ValueError):
            return None
        local = datetime(year, month, day, hour, minute, tzinfo=tariff_zone())
        return local.astimezone(timezone.utc)

    @classmethod
    def _latest_series_value(
        cls,
        infos: list[dict[str, Any]],
        label: str,
        *,
        local_date: str,
    ) -> tuple[float, Optional[datetime]]:
        """Return the most recent non-idle sample from a labelled day series."""
        by_label: dict[str, list[dict[str, Any]]] = {
            str(series.get("label") or ""): (series.get("records") or []) for series in infos
        }
        records = by_label.get(label, [])
        floor = cls._POWER_NOISE_FLOOR_W
        for record in reversed(records):
            try:
                value = float(record.get("value"))
            except (TypeError, ValueError):
                continue
            if value <= floor:
                continue
            sample_at = cls._series_sample_time(local_date, record.get("time"))
            return value, sample_at
        return 0.0, None

    async def _daily_day_data(
        self, plant_id: str
    ) -> tuple[dict[str, float], float, Optional[datetime]]:
        local_date = tariff_now().strftime("%Y-%m-%d")
        now = time.monotonic()
        if self._daily_cache is not None:
            expiry, cached_date, totals, latest_load_w, latest_load_at = self._daily_cache
            if cached_date == local_date and now < expiry:
                return totals, latest_load_w, latest_load_at
        response = await self._request(
            "GET",
            f"/api/v1/plant/energy/{plant_id}/day",
            params={"date": local_date, "id": plant_id, "lan": "en"},
        )
        data = response.json().get("data") or {}
        infos = data.get("infos") or []
        totals = self._integrate_day_series(infos)
        latest_load_w, latest_load_at = self._latest_series_value(
            infos, "Load", local_date=local_date
        )
        self._daily_cache = (
            now + _DAILY_TOTALS_TTL_SECONDS,
            local_date,
            totals,
            latest_load_w,
            latest_load_at,
        )
        return totals, latest_load_w, latest_load_at

    async def _daily_totals(self, plant_id: str) -> dict[str, float]:
        totals, _, _ = await self._daily_day_data(plant_id)
        return totals

    async def _recent_typical_house_load(self) -> Optional[tuple[float, datetime]]:
        """Median house load from recent sampler rows when the live CT reads zero."""
        from sqlalchemy import select

        from app.db.models import MetricSampleRow
        from app.db.session import SessionLocal

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
        async with SessionLocal() as db:
            result = await db.execute(
                select(MetricSampleRow.house_load_w, MetricSampleRow.timestamp)
                .where(MetricSampleRow.timestamp >= cutoff)
                .where(MetricSampleRow.house_load_w > 50)
                .order_by(MetricSampleRow.timestamp.desc())
                .limit(120)
            )
            rows = result.all()
        if len(rows) < 3:
            return None
        values = sorted(row[0] for row in rows)
        median = values[len(values) // 2]
        latest_at = max(row[1] for row in rows)
        if latest_at.tzinfo is None:
            latest_at = latest_at.replace(tzinfo=timezone.utc)
        return median, latest_at

    def _apply_house_load_fallbacks(
        self,
        metrics: LiveMetrics,
        *,
        latest_load_w: float,
        latest_load_at: Optional[datetime],
        recent_typical: Optional[tuple[float, datetime]],
    ) -> None:
        floor = self._POWER_NOISE_FLOOR_W
        if metrics.house_load_source != HouseLoadSource.MINIMAL:
            return
        if latest_load_w > floor:
            metrics.house_load_w = latest_load_w
            metrics.house_load_source = HouseLoadSource.DAY_SERIES
            metrics.house_load_at = latest_load_at
            return
        if recent_typical is not None:
            metrics.house_load_w = recent_typical[0]
            metrics.house_load_source = HouseLoadSource.RECENT_TYPICAL
            metrics.house_load_at = recent_typical[1]

    async def get_live_metrics(self) -> LiveMetrics:
        await self._authenticate()
        plant_id = await self._plant_id()
        response = await self._request("GET", f"/api/v1/plant/energy/{plant_id}/flow")
        metrics = self._parse_flow(response.json())
        latest_load_w = 0.0
        latest_load_at: Optional[datetime] = None
        try:
            totals, latest_load_w, latest_load_at = await self._daily_day_data(plant_id)
            # Prefer /flow etoday* counters (set in _parse_flow); fill gaps from day series.
            if metrics.daily_pv_kwh <= 0 and totals["pv"] > 0:
                metrics.daily_pv_kwh = totals["pv"]
            if metrics.daily_import_kwh <= 0 and totals["import"] > 0:
                metrics.daily_import_kwh = totals["import"]
            if metrics.daily_export_kwh <= 0 and totals["export"] > 0:
                metrics.daily_export_kwh = totals["export"]
        except (AdapterError, httpx.HTTPError, KeyError, ValueError):
            pass
        recent_typical: Optional[tuple[float, datetime]] = None
        if metrics.house_load_source == HouseLoadSource.MINIMAL:
            try:
                recent_typical = await self._recent_typical_house_load()
            except Exception:
                recent_typical = None
        self._apply_house_load_fallbacks(
            metrics,
            latest_load_w=latest_load_w,
            latest_load_at=latest_load_at,
            recent_typical=recent_typical,
        )
        return finalize_live_metrics(metrics)

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
