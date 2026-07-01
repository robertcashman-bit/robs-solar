"""Live vs summary daily totals should match on the dashboard."""

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_day_summary_matches_live_daily_kwh(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    live = await client.get("/metrics/live")
    summary = await client.get("/metrics/summary?range=day")
    assert live.status_code == 200
    assert summary.status_code == 200
    live_body = live.json()
    summary_body = summary.json()
    assert summary_body["pv_kwh"] == pytest.approx(live_body["daily_pv_kwh"], abs=0.01)
    assert summary_body["import_kwh"] == pytest.approx(live_body["daily_import_kwh"], abs=0.01)
    assert summary_body["export_kwh"] == pytest.approx(live_body["daily_export_kwh"], abs=0.01)
