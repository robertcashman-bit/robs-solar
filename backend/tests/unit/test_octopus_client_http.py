"""HTTP-level tests for OctopusClient using a mocked transport.

These never call the real Octopus API; a MockTransport answers the account,
tariff rate, and Agile endpoints so we can assert parsing/selection logic.
"""

import httpx
import pytest

from app.services.octopus_client import OctopusClient, OctopusCredentials

ACCOUNT_JSON = {
    "number": "A-TEST",
    "properties": [
        {
            "electricity_meter_points": [
                {
                    "mpan": "1900000000001",
                    "is_export": True,
                    "meters": [{"serial_number": "EXPORTSER"}],
                    "agreements": [
                        {"tariff_code": "E-1R-OUTGOING-VAR-24-10-26-J", "valid_to": None}
                    ],
                },
                {
                    "mpan": "1900000000002",
                    "is_export": False,
                    "meters": [
                        {"serial_number": "OLD"},
                        {"serial_number": "IMPORTSER"},
                    ],
                    "agreements": [
                        {
                            "tariff_code": "E-2R-OLD-22-11-01-J",
                            "valid_to": "2025-01-01T00:00:00Z",
                        },
                        {
                            "tariff_code": "E-1R-IOG-KDP-FIX-12M-25-06-20-J",
                            "valid_to": None,
                        },
                    ],
                },
            ]
        }
    ],
}

IMPORT_RATES = {
    "results": [
        {
            "value_inc_vat": 25.89,
            "valid_from": "2025-06-19T23:00:00Z",
            "valid_to": "2026-03-31T23:00:00Z",
        },
        {
            "value_inc_vat": 22.38,
            "valid_from": "2026-03-31T23:00:00Z",
            "valid_to": None,
        },
    ]
}

EXPORT_RATES = {
    "results": [
        {
            "value_inc_vat": 15.0,
            "valid_from": "2024-10-25T23:00:00Z",
            "valid_to": "2026-03-01T00:00:00Z",
        },
        {"value_inc_vat": 12.0, "valid_from": "2026-03-01T00:00:00Z", "valid_to": None},
    ]
}

AGILE_RATES_UNSORTED = {
    "results": [
        {
            "value_inc_vat": 30.0,
            "valid_from": "2026-06-29T20:30:00Z",
            "valid_to": "2026-06-29T21:00:00Z",
        },
        {
            "value_inc_vat": 18.6,
            "valid_from": "2026-06-29T07:30:00Z",
            "valid_to": "2026-06-29T08:00:00Z",
        },
        {
            "value_inc_vat": 24.5,
            "valid_from": "2026-06-29T21:30:00Z",
            "valid_to": "2026-06-29T22:00:00Z",
        },
    ]
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/accounts/A-TEST/":
        return httpx.Response(200, json=ACCOUNT_JSON)
    if "IOG-KDP-FIX-12M-25-06-20" in path:
        return httpx.Response(200, json=IMPORT_RATES)
    if "OUTGOING-VAR-24-10-26" in path:
        return httpx.Response(200, json=EXPORT_RATES)
    if "AGILE-24-10-01" in path:
        return httpx.Response(200, json=AGILE_RATES_UNSORTED)
    return httpx.Response(404, json={"detail": "not found"})


def _make_client() -> OctopusClient:
    client = OctopusClient()
    client.update_credentials(OctopusCredentials(api_key="k", account_number="A-TEST", region="J"))
    client._client = httpx.AsyncClient(
        base_url="https://api.test",
        transport=httpx.MockTransport(_handler),
        timeout=5.0,
    )
    return client


@pytest.mark.asyncio
async def test_get_tariff_info_parses_import_and_export_rates() -> None:
    client = _make_client()
    info = await client.get_tariff_info()
    assert info.tariff_family == "IOG"
    assert info.region == "J"
    assert info.import_tariff_code == "E-1R-IOG-KDP-FIX-12M-25-06-20-J"
    assert info.export_tariff_code == "E-1R-OUTGOING-VAR-24-10-26-J"
    # Picks the currently-active rate (open-ended valid_to), not the expired one.
    assert info.import_rate_pence == pytest.approx(22.38)
    assert info.export_rate_pence == pytest.approx(12.0)


@pytest.mark.asyncio
async def test_rate_gbp_helpers_divide_by_100() -> None:
    client = _make_client()
    assert await client.get_import_rate_gbp() == pytest.approx(0.2238)
    assert await client.get_export_rate_gbp() == pytest.approx(0.12)


@pytest.mark.asyncio
async def test_get_agile_rates_sorted_ascending_by_time() -> None:
    client = _make_client()
    rates = await client.get_agile_rates()
    times = [r["valid_from"] for r in rates]
    assert times == sorted(times)
    assert rates[0]["valid_from"] == "2026-06-29T07:30:00Z"


@pytest.mark.asyncio
async def test_resolve_tariffs_caches_codes_on_credentials() -> None:
    client = _make_client()
    await client.resolve_tariffs_from_account()
    assert client.credentials.import_tariff_code == "E-1R-IOG-KDP-FIX-12M-25-06-20-J"
    assert client.credentials.export_tariff_code == "E-1R-OUTGOING-VAR-24-10-26-J"


@pytest.mark.asyncio
async def test_tariff_info_empty_when_not_configured() -> None:
    client = OctopusClient()
    client.update_credentials(OctopusCredentials(api_key=""))
    info = await client.get_tariff_info()
    assert info.import_rate_pence is None
    assert info.tariff_family == ""
