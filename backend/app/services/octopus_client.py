"""Octopus Energy API client (account tariffs, Agile reference, consumption)."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings
from app.schemas.domain import (
    DispatchResponse,
    DispatchWindow,
    OctopusMeterPower,
    OctopusRatePlan,
    OffPeakWindow,
)

OCTOPUS_BASE = "https://api.octopus.energy/v1"
KRAKEN_GRAPHQL = "https://api.octopus.energy/v1/graphql/"

# Current Agile import product (market reference for scheduler overlay).
DEFAULT_AGILE_PRODUCT = "AGILE-24-10-01"

_TARIFF_CODE_RE = re.compile(r"^E-\dR-(.+)-([A-P])$", re.IGNORECASE)


@dataclass
class OctopusCredentials:
    api_key: str = ""
    account_number: str = ""
    mpan: str = ""
    meter_serial: str = ""
    region: str = "C"
    import_tariff_code: str = ""
    export_tariff_code: str = ""
    product_code: str = DEFAULT_AGILE_PRODUCT

    @property
    def agile_tariff_code(self) -> str:
        return f"E-1R-{self.product_code}-{self.region}"


@dataclass
class OctopusTariffInfo:
    import_tariff_code: str = ""
    import_product_code: str = ""
    import_display_name: str = ""
    import_rate_pence: float | None = None
    export_tariff_code: str = ""
    export_product_code: str = ""
    export_display_name: str = ""
    export_rate_pence: float | None = None
    standing_charge_pence: float | None = None
    is_variable: bool = False
    tariff_family: str = ""
    region: str = ""


def parse_tariff_code(code: str) -> tuple[str, str]:
    """Return (product_code, region) from an Octopus tariff code."""
    match = _TARIFF_CODE_RE.match(code.strip())
    if not match:
        return "", ""
    return match.group(1), match.group(2).upper()


def tariff_family_from_code(code: str) -> str:
    upper = code.upper()
    if "AGILE" in upper:
        return "AGILE"
    if "IOG" in upper or "-GO-" in upper:
        return "IOG"
    if "OUTGOING" in upper:
        return "OUTGOING"
    if "FLUX" in upper:
        return "FLUX"
    if "COSY" in upper:
        return "COSY"
    return "FIXED"


def _credentials_from_settings() -> OctopusCredentials:
    return OctopusCredentials(
        api_key=settings.octopus_api_key,
        account_number=settings.octopus_account_number,
        mpan=settings.octopus_mpan,
        meter_serial=settings.octopus_meter_serial,
        region=(settings.octopus_region or "C").upper(),
    )


def _active_agreement(agreements: list[dict[str, Any]]) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc)
    for agreement in reversed(agreements):
        valid_to = agreement.get("valid_to")
        if valid_to:
            try:
                end = datetime.fromisoformat(valid_to.replace("Z", "+00:00"))
                if end <= now:
                    continue
            except ValueError:
                pass
        if agreement.get("tariff_code"):
            return agreement
    return agreements[-1] if agreements else None


def _pick_meter_serial(meters: list[dict[str, Any]]) -> str:
    if not meters:
        return ""
    for meter in reversed(meters):
        serial = meter.get("serial_number", "")
        if serial:
            return serial
    return ""


def parse_consumption_interval(raw: dict[str, Any]) -> tuple[datetime, datetime, float] | None:
    start_raw = raw.get("interval_start")
    end_raw = raw.get("interval_end")
    if not start_raw or not end_raw:
        return None
    try:
        start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    try:
        kwh = float(raw.get("consumption") or 0)
    except (TypeError, ValueError):
        kwh = 0.0
    return start, end, kwh


def consumption_average_power_w(kwh: float, start: datetime, end: datetime) -> float:
    hours = (end - start).total_seconds() / 3600.0
    if hours <= 0:
        return 0.0
    return round(kwh / hours * 1000.0, 1)


def pick_consumption_interval_for_display(
    raw_intervals: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime, float, bool] | None:
    """Prefer the in-progress half hour; else the most recent completed interval."""
    if now is None:
        now = datetime.now(timezone.utc)
    parsed: list[tuple[datetime, datetime, float]] = []
    for raw in raw_intervals:
        interval = parse_consumption_interval(raw)
        if interval is not None:
            parsed.append(interval)
    if not parsed:
        return None
    parsed.sort(key=lambda row: row[0], reverse=True)
    for start, end, kwh in parsed:
        if start <= now < end:
            return start, end, kwh, True
    for start, end, kwh in parsed:
        if end <= now:
            return start, end, kwh, False
    start, end, kwh = parsed[0]
    return start, end, kwh, start <= now < end


class OctopusClient:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[datetime, Any]] = {}
        self._creds = _credentials_from_settings()
        self._kraken_token: str | None = None
        self._kraken_token_expires: datetime | None = None
        self._client = httpx.AsyncClient(
            base_url=OCTOPUS_BASE,
            timeout=15.0,
            headers=self._auth_headers(),
        )
        self._graphql_client = httpx.AsyncClient(timeout=20.0)

    def _auth_headers(self, api_key: str | None = None) -> dict[str, str]:
        key = api_key if api_key is not None else self._creds.api_key
        if not key:
            return {}
        token = base64.b64encode(f"{key}:".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    @property
    def credentials(self) -> OctopusCredentials:
        return self._creds

    def update_credentials(self, creds: OctopusCredentials) -> None:
        creds.region = (creds.region or "C").upper()
        if not creds.product_code:
            creds.product_code = DEFAULT_AGILE_PRODUCT
        self._creds = creds
        headers = self._auth_headers()
        if headers:
            self._client.headers.update(headers)
        else:
            self._client.headers.pop("Authorization", None)
        self._cache.clear()
        self._kraken_token = None
        self._kraken_token_expires = None

    async def _obtain_kraken_token(self) -> str:
        now = datetime.now(timezone.utc)
        if (
            self._kraken_token
            and self._kraken_token_expires
            and now < self._kraken_token_expires
        ):
            return self._kraken_token
        if not self._creds.api_key:
            raise ValueError("Octopus API key not configured")
        mutation = """
        mutation ObtainKrakenToken($input: ObtainJSONWebTokenInput!) {
          obtainKrakenToken(input: $input) { token }
        }
        """
        response = await self._graphql_client.post(
            KRAKEN_GRAPHQL,
            json={
                "query": mutation,
                "variables": {"input": {"APIKey": self._creds.api_key}},
            },
        )
        response.raise_for_status()
        body = response.json()
        if body.get("errors"):
            raise ValueError(body["errors"][0].get("message", "Kraken auth failed"))
        token = body["data"]["obtainKrakenToken"]["token"]
        self._kraken_token = token
        # Tokens last ~60 minutes; refresh early.
        self._kraken_token_expires = now + timedelta(minutes=50)
        return token

    @staticmethod
    def _parse_dispatch_row(row: dict[str, Any]) -> DispatchWindow | None:
        start_raw = row.get("start")
        end_raw = row.get("end")
        if not start_raw or not end_raw:
            return None
        try:
            start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
        except ValueError:
            return None
        delta_raw = row.get("delta")
        delta_kwh: float | None = None
        if delta_raw is not None:
            try:
                delta_kwh = abs(float(delta_raw))
            except (TypeError, ValueError):
                delta_kwh = None
        meta = row.get("meta") or {}
        return DispatchWindow(
            start=start,
            end=end,
            source=str(meta.get("source") or ""),
            delta_kwh=delta_kwh,
        )

    async def get_dispatches(self) -> DispatchResponse:
        """Fetch IOG off-peak window plus planned/completed smart-charge dispatches."""
        off_peak = OffPeakWindow(
            start=settings.iog_offpeak_start,
            end=settings.iog_offpeak_end,
        )
        if not self.configured() or not self._creds.account_number:
            return DispatchResponse(off_peak_window=off_peak)

        async def fetch() -> DispatchResponse:
            token = await self._obtain_kraken_token()
            query = """
            query GetDispatches($accountNumber: String!) {
              plannedDispatches(accountNumber: $accountNumber) {
                start end delta meta { source }
              }
              completedDispatches(accountNumber: $accountNumber) {
                start end delta meta { source }
              }
            }
            """
            response = await self._graphql_client.post(
                KRAKEN_GRAPHQL,
                json={
                    "query": query,
                    "variables": {"accountNumber": self._creds.account_number},
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            body = response.json()
            if body.get("errors"):
                raise ValueError(body["errors"][0].get("message", "Dispatch query failed"))
            data = body.get("data") or {}
            planned = [
                w
                for row in data.get("plannedDispatches") or []
                if (w := self._parse_dispatch_row(row))
            ]
            completed = [
                w
                for row in data.get("completedDispatches") or []
                if (w := self._parse_dispatch_row(row))
            ]
            tariff = await self.get_tariff_info()
            return DispatchResponse(
                off_peak_window=off_peak,
                planned=planned,
                completed=completed,
                tariff_family=tariff.tariff_family,
            )

        return await self._get_cached("dispatches", 300, fetch)

    def configured(self) -> bool:
        return bool(self._creds.api_key)

    async def _get_cached(self, key: str, ttl_seconds: int, fetcher) -> Any:
        now = datetime.now(timezone.utc)
        if key in self._cache:
            cached_at, data = self._cache[key]
            if (now - cached_at).total_seconds() < ttl_seconds:
                return data
        data = await fetcher()
        self._cache[key] = (now, data)
        return data

    async def resolve_tariffs_from_account(self) -> OctopusTariffInfo:
        """Fetch account and cache active import/export tariff codes on credentials."""
        account = await self.get_account()
        info = self._tariff_info_from_account(account)
        if info.import_tariff_code:
            self._creds.import_tariff_code = info.import_tariff_code
        if info.export_tariff_code:
            self._creds.export_tariff_code = info.export_tariff_code
        if info.region:
            self._creds.region = info.region
        return info

    def _tariff_info_from_account(self, account: dict[str, Any]) -> OctopusTariffInfo:
        info = OctopusTariffInfo(region=self._creds.region)
        for prop in account.get("properties", []):
            for point in prop.get("electricity_meter_points", []):
                agreement = _active_agreement(point.get("agreements", []))
                if not agreement:
                    continue
                code = agreement.get("tariff_code", "")
                product, region = parse_tariff_code(code)
                if point.get("is_export"):
                    info.export_tariff_code = code
                    info.export_product_code = product
                    info.export_display_name = product.replace("-", " ")
                else:
                    info.import_tariff_code = code
                    info.import_product_code = product
                    info.import_display_name = product.replace("-", " ")
                    info.tariff_family = tariff_family_from_code(code)
                    info.is_variable = info.tariff_family == "AGILE"
                    if region:
                        info.region = region
        return info

    async def _current_standard_rate_pence(
        self, product_code: str, tariff_code: str
    ) -> float | None:
        if not product_code or not tariff_code:
            return None

        async def fetch() -> float | None:
            url = (
                f"/products/{product_code}/electricity-tariffs/"
                f"{tariff_code}/standard-unit-rates/"
            )
            response = await self._client.get(url, params={"page_size": 10})
            response.raise_for_status()
            results = response.json().get("results", [])
            if not results:
                return None
            now = datetime.now(timezone.utc)

            def valid_at(row: dict[str, Any]) -> bool:
                start = datetime.fromisoformat(row["valid_from"].replace("Z", "+00:00"))
                if start > now:
                    return False
                end_raw = row.get("valid_to")
                if not end_raw:
                    return True
                end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
                return end > now

            current = next((r for r in reversed(results) if valid_at(r)), results[-1])
            return float(current["value_inc_vat"])

        cache_key = f"std_rate:{tariff_code}"
        return await self._get_cached(cache_key, 3600, fetch)

    async def get_tariff_info(self) -> OctopusTariffInfo:
        if not self.configured():
            return OctopusTariffInfo()

        async def fetch() -> OctopusTariffInfo:
            base = await self.resolve_tariffs_from_account()
            if base.import_product_code and base.import_tariff_code:
                base.import_rate_pence = await self._current_standard_rate_pence(
                    base.import_product_code, base.import_tariff_code
                )
            if base.export_product_code and base.export_tariff_code:
                base.export_rate_pence = await self._current_standard_rate_pence(
                    base.export_product_code, base.export_tariff_code
                )
            return base

        return await self._get_cached("tariff_info", 3600, fetch)

    async def get_import_rate_gbp(self) -> float | None:
        info = await self.get_tariff_info()
        if info.import_rate_pence is not None:
            return info.import_rate_pence / 100.0
        return None

    async def get_export_rate_gbp(self) -> float | None:
        info = await self.get_tariff_info()
        if info.export_rate_pence is not None:
            return info.export_rate_pence / 100.0
        return None

    async def get_agile_rates(self, hours: int = 24) -> list[dict[str, Any]]:
        if not self.configured():
            return []

        async def fetch() -> list[dict[str, Any]]:
            now = datetime.now(timezone.utc)
            period_from = now.isoformat()
            period_to = (now + timedelta(hours=hours)).isoformat()
            url = (
                f"/products/{DEFAULT_AGILE_PRODUCT}/electricity-tariffs/"
                f"E-1R-{DEFAULT_AGILE_PRODUCT}-{self._creds.region}/standard-unit-rates/"
            )
            response = await self._client.get(
                url,
                params={"period_from": period_from, "period_to": period_to},
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            rates = [
                {
                    "valid_from": r["valid_from"],
                    "valid_to": r["valid_to"],
                    "value_inc_vat": float(r["value_inc_vat"]),
                }
                for r in results
            ]
            rates.sort(key=lambda r: r["valid_from"])
            return rates

        return await self._get_cached("agile_rates", 300, fetch)

    async def get_import_unit_rates(self, hours: int = 48) -> list[dict[str, Any]]:
        """Half-hourly or standard unit rates for the user's own import tariff."""
        if not self.configured():
            return []
        info = await self.get_tariff_info()
        if not info.import_product_code or not info.import_tariff_code:
            return []

        async def fetch() -> list[dict[str, Any]]:
            now = datetime.now(timezone.utc)
            period_from = now.isoformat()
            period_to = (now + timedelta(hours=hours)).isoformat()
            url = (
                f"/products/{info.import_product_code}/electricity-tariffs/"
                f"{info.import_tariff_code}/standard-unit-rates/"
            )
            response = await self._client.get(
                url,
                params={"period_from": period_from, "period_to": period_to},
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            rates = [
                {
                    "valid_from": r["valid_from"],
                    "valid_to": r["valid_to"],
                    "value_inc_vat": float(r["value_inc_vat"]),
                }
                for r in results
            ]
            rates.sort(key=lambda row: row["valid_from"])
            return rates

        cache_key = f"import_rates:{info.import_tariff_code}:{hours}"
        return await self._get_cached(cache_key, 3600, fetch)

    async def get_rate_plan(self) -> OctopusRatePlan:
        from app.config import settings as app_settings
        from app.services.octopus_rate_plan import derive_rate_plan

        if not self.configured():
            return OctopusRatePlan(configured=False)

        info = await self.get_tariff_info()
        rates = await self.get_import_unit_rates(hours=48)
        offpeak_start = app_settings.iog_offpeak_start
        offpeak_end = app_settings.iog_offpeak_end
        planned = []
        try:
            dispatches = await self.get_dispatches()
            offpeak_start = dispatches.off_peak_window.start
            offpeak_end = dispatches.off_peak_window.end
            planned = list(dispatches.planned)
        except Exception:  # noqa: BLE001
            pass

        return derive_rate_plan(
            rates,
            tariff_family=info.tariff_family,
            region=info.region,
            import_display_name=info.import_display_name,
            standing_charge_pence=info.standing_charge_pence,
            offpeak_start=offpeak_start,
            offpeak_end=offpeak_end,
            planned=planned,
        )

    async def get_unit_rates(self, hours: int = 24) -> list[dict[str, Any]]:
        """Agile half-hourly rates (market reference). Prefer get_tariff_info for your bill."""
        return await self.get_agile_rates(hours=hours)

    async def get_consumption(self, page_size: int = 48) -> list[dict[str, Any]]:
        if not self.configured() or not self._creds.mpan or not self._creds.meter_serial:
            return []

        async def fetch() -> list[dict[str, Any]]:
            url = (
                f"/electricity-meter-points/{self._creds.mpan}/"
                f"meters/{self._creds.meter_serial}/consumption/"
            )
            response = await self._client.get(url, params={"page_size": page_size})
            response.raise_for_status()
            return response.json().get("results", [])

        return await self._get_cached("consumption", 600, fetch)

    async def get_meter_power_estimate(self) -> OctopusMeterPower:
        if not self.configured():
            return OctopusMeterPower(configured=False, message="Octopus API not configured")
        if not self._creds.mpan or not self._creds.meter_serial:
            return OctopusMeterPower(
                configured=False,
                message="Meter MPAN or serial not configured — use Settings → Octopus",
            )

        async def fetch() -> OctopusMeterPower:
            url = (
                f"/electricity-meter-points/{self._creds.mpan}/"
                f"meters/{self._creds.meter_serial}/consumption/"
            )
            response = await self._client.get(url, params={"page_size": 4})
            response.raise_for_status()
            raw_intervals = response.json().get("results", [])
            picked = pick_consumption_interval_for_display(raw_intervals)
            if picked is None:
                return OctopusMeterPower(
                    configured=True,
                    message="No meter readings available yet from Octopus",
                )
            start, end, kwh, is_current = picked
            return OctopusMeterPower(
                configured=True,
                average_power_w=consumption_average_power_w(kwh, start, end),
                consumption_kwh=round(kwh, 4),
                interval_start=start,
                interval_end=end,
                is_current_interval=is_current,
                message="",
            )

        return await self._get_cached("meter_power", 120, fetch)

    async def get_account(self) -> dict[str, Any]:
        if not self.configured() or not self._creds.account_number:
            return {}

        async def fetch() -> dict[str, Any]:
            response = await self._client.get(f"/accounts/{self._creds.account_number}/")
            response.raise_for_status()
            return response.json()

        return await self._get_cached("account", 3600, fetch)

    async def discover(self, api_key: str, account_number: str) -> dict[str, str]:
        headers = self._auth_headers(api_key)
        async with httpx.AsyncClient(
            base_url=OCTOPUS_BASE, timeout=15.0, headers=headers
        ) as client:
            response = await client.get(f"/accounts/{account_number}/")
            response.raise_for_status()
            data = response.json()

        for prop in data.get("properties", []):
            for point in prop.get("electricity_meter_points", []):
                if point.get("is_export"):
                    continue
                mpan = point.get("mpan", "")
                serial = _pick_meter_serial(point.get("meters", []))
                agreement = _active_agreement(point.get("agreements", []))
                code = agreement.get("tariff_code", "") if agreement else ""
                _, region = parse_tariff_code(code)
                return {
                    "account_number": account_number,
                    "mpan": mpan,
                    "meter_serial": serial,
                    "region": region,
                    "import_tariff_code": code,
                }
        return {
            "account_number": account_number,
            "mpan": "",
            "meter_serial": "",
            "region": "",
            "import_tariff_code": "",
        }

    @staticmethod
    def _region_from_agreements(agreements: list[dict[str, Any]]) -> str:
        agreement = _active_agreement(agreements)
        if not agreement:
            return ""
        _, region = parse_tariff_code(agreement.get("tariff_code", ""))
        return region


octopus_client = OctopusClient()
