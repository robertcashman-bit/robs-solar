"""Read-only: poll battery SOC + flow every 3 minutes and log the trend."""

from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from app.adapters.sunsynk_auth import login
from app.config import settings


async def main(rounds: int = 8, interval_s: int = 180) -> None:
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
    plant_id = settings.sunsynk_plant_id
    try:
        prev = None
        for _ in range(rounds):
            flow = await client.get(f"/api/v1/plant/energy/{plant_id}/flow")
            f = flow.json().get("data") or {}
            soc = f.get("soc")
            ts = datetime.now().strftime("%H:%M:%S")
            delta = "" if prev is None else f" (Δ {soc - prev:+.1f})"
            print(
                f"{ts} SOC={soc}%{delta}  pv={f.get('pvPower')}W "
                f"load={f.get('loadOrEpsPower')}W batt={f.get('battPower')}W "
                f"grid={f.get('gridOrMeterPower')}W",
                flush=True,
            )
            prev = soc
            await asyncio.sleep(interval_s)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
