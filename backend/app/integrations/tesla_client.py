"""Tesla Fleet API client for EV charging visibility."""

from __future__ import annotations

from typing import Any

import httpx

from app.schemas.finance import TeslaConfig

TESLA_TOKEN_URL = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token"
TESLA_API_BASE = "https://fleet-api.prd.eu.vn.cloud.tesla.com"


class TeslaError(Exception):
    pass


class TeslaClient:
    def __init__(self, config: TeslaConfig) -> None:
        self._config = config

    @property
    def configured(self) -> bool:
        return bool(
            self._config.client_id
            and self._config.client_secret
            and self._config.refresh_token
        )

    async def get_access_token(self) -> str:
        if not self.configured:
            raise TeslaError("Tesla is not configured")
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                TESLA_TOKEN_URL,
                json={
                    "grant_type": "refresh_token",
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                    "refresh_token": self._config.refresh_token,
                },
            )
        if response.status_code >= 400:
            raise TeslaError(f"Tesla token refresh failed: {response.text}")
        token = response.json().get("access_token")
        if not token:
            raise TeslaError("Tesla token response missing access_token")
        return str(token)

    async def _auth_get(self, path: str) -> dict[str, Any]:
        token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=20.0, base_url=TESLA_API_BASE) as client:
            response = await client.get(
                path,
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code >= 400:
            raise TeslaError(f"Tesla API {path} failed: {response.text}")
        return response.json()

    async def list_vehicles(self) -> list[dict[str, Any]]:
        payload = await self._auth_get("/api/1/vehicles")
        return payload.get("response", [])

    async def get_vehicle_data(self, vehicle_id: str) -> dict[str, Any]:
        payload = await self._auth_get(f"/api/1/vehicles/{vehicle_id}/vehicle_data")
        return payload.get("response", {})

    async def get_energy_live_status(self, site_id: str) -> dict[str, Any]:
        payload = await self._auth_get(f"/api/1/energy_sites/{site_id}/live_status")
        return payload.get("response", {})
