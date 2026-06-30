"""Read-only: print live flow + battery SOC and the account's write permission."""

from __future__ import annotations

import asyncio

import httpx

from app.adapters.sunsynk_auth import login
from app.config import settings


async def main() -> None:
    client = httpx.AsyncClient(
        base_url=settings.sunsynk_base_url.rstrip("/"),
        timeout=settings.sunsynk_timeout_seconds,
    )
    data = await login(
        client,
        username=settings.sunsynk_username,
        plain_password=settings.sunsynk_password,
    )
    client.headers["Authorization"] = f"Bearer {data['access_token']}"
    try:
        plant_id = settings.sunsynk_plant_id
        detail = await client.get(f"/api/v1/plant/{plant_id}?lan=en")
        dd = detail.json().get("data") or {}
        print(f"plantPermission={dd.get('plantPermission')}")
        print(f"master={dd.get('master')} installer={dd.get('installer')}")

        flow = await client.get(f"/api/v1/plant/energy/{plant_id}/flow")
        f = flow.json().get("data") or {}
        print(
            f"SOC={f.get('soc')}%  pvPower={f.get('pvPower')}W  "
            f"load={f.get('loadOrEpsPower')}W  battPower={f.get('battPower')}W  "
            f"grid={f.get('gridOrMeterPower')}W"
        )
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
