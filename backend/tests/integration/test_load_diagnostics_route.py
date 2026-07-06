"""Integration tests for GET /metrics/diagnostics."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_diagnostics_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/metrics/diagnostics")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_viewer_can_read_diagnostics(client: AsyncClient) -> None:
    from app.services.live_metrics_cache import live_metrics_cache

    live_metrics_cache._metrics = None
    live_metrics_cache._fetched_at = None

    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/diagnostics")
    assert response.status_code == 200
    body = response.json()

    for key in (
        "timestamp",
        "adapter_mode",
        "data_source",
        "is_cached",
        "pv",
        "battery",
        "grid_import",
        "grid_export",
        "measured_load_w",
        "measured_load_origin",
        "estimated_load_w",
        "estimated_load_formula",
        "house_load_source",
        "house_load_w",
    ):
        assert key in body, f"missing diagnostics key: {key}"

    # Simulator mode: no raw cloud payload, but power-flow fields are still real.
    assert body["adapter_mode"] == "simulator"
    assert body["raw_payload"] is None
    assert body["raw_payload_note"]
    assert body["pv"]["origin"] in ("live", "cached")
    assert body["pv"]["value"] is not None
    assert body["estimated_load_formula"] == (
        "pv_power_w + grid_import_w - grid_export_w + battery_power_w"
    )


@pytest.mark.asyncio
async def test_diagnostics_never_silently_returns_zero_for_unknown_fields(
    client: AsyncClient,
) -> None:
    """Fields that genuinely cannot be determined must be reported as unknown,
    never coerced into a plausible-looking 0."""
    await login(client, "viewer", "viewer-pass")
    response = await client.get("/metrics/diagnostics")
    assert response.status_code == 200
    body = response.json()
    for field_key in ("pv", "battery", "grid_import", "grid_export"):
        field = body[field_key]
        if field["value"] is None:
            assert field["origin"] == "unknown"
