"""Unit tests for OctopusClient credential + tariff parsing."""

from app.services.octopus_client import (
    DEFAULT_AGILE_PRODUCT,
    OctopusClient,
    OctopusCredentials,
    parse_tariff_code,
    tariff_family_from_code,
)


def test_agile_tariff_code_uses_region_and_product() -> None:
    creds = OctopusCredentials(api_key="k", region="J")
    assert creds.product_code == DEFAULT_AGILE_PRODUCT
    assert creds.agile_tariff_code == f"E-1R-{DEFAULT_AGILE_PRODUCT}-J"


def test_parse_tariff_code_iog() -> None:
    product, region = parse_tariff_code("E-1R-IOG-KDP-FIX-12M-25-06-20-J")
    assert product == "IOG-KDP-FIX-12M-25-06-20"
    assert region == "J"


def test_tariff_family_iog() -> None:
    assert tariff_family_from_code("E-1R-IOG-KDP-FIX-12M-25-06-20-J") == "IOG"


def test_update_credentials_normalises_region_and_clears_cache() -> None:
    client = OctopusClient()
    client._cache["agile_rates"] = (None, ["stale"])  # type: ignore[assignment]
    client.update_credentials(OctopusCredentials(api_key="k", region="c", product_code=""))
    assert client.configured() is True
    assert client.credentials.region == "C"
    assert client.credentials.product_code == DEFAULT_AGILE_PRODUCT
    assert "agile_rates" not in client._cache


def test_region_from_agreements_reads_active_tariff() -> None:
    agreements = [
        {"tariff_code": "E-2R-OLD-22-11-01-A", "valid_to": "2025-01-01T00:00:00Z"},
        {"tariff_code": "E-1R-IOG-KDP-FIX-12M-25-06-20-J", "valid_to": None},
    ]
    assert OctopusClient._region_from_agreements(agreements) == "J"


def test_region_from_agreements_handles_empty() -> None:
    assert OctopusClient._region_from_agreements([]) == ""


def test_update_credentials_preserves_authorization_header() -> None:
    client = OctopusClient()
    client.update_credentials(OctopusCredentials(api_key="test-key"))
    assert client._client.headers.get("Authorization", "").startswith("Basic ")


def test_empty_api_key_means_not_configured() -> None:
    client = OctopusClient()
    client.update_credentials(OctopusCredentials(api_key=""))
    assert client.configured() is False


def test_tariff_info_from_account_parses_import_and_export() -> None:
    client = OctopusClient()
    account = {
        "properties": [
            {
                "electricity_meter_points": [
                    {
                        "is_export": True,
                        "agreements": [
                            {
                                "tariff_code": "E-1R-OUTGOING-VAR-24-10-26-J",
                                "valid_to": None,
                            }
                        ],
                    },
                    {
                        "is_export": False,
                        "agreements": [
                            {
                                "tariff_code": "E-1R-IOG-KDP-FIX-12M-25-06-20-J",
                                "valid_to": None,
                            }
                        ],
                    },
                ]
            }
        ]
    }
    info = client._tariff_info_from_account(account)
    assert info.import_tariff_code == "E-1R-IOG-KDP-FIX-12M-25-06-20-J"
    assert info.export_tariff_code == "E-1R-OUTGOING-VAR-24-10-26-J"
    assert info.tariff_family == "IOG"
    assert info.region == "J"
