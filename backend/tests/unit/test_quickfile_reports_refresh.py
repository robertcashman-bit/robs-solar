"""Auto-refresh stored QuickFile reports when credentials are present."""

import json
from types import SimpleNamespace

import pytest

from app.schemas.finance import QuickFileConfig, QuickFileReportsResponse
from app.services.finance.quickfile_reports_service import QuickFileReportsService


@pytest.mark.asyncio
async def test_get_or_refresh_returns_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    service = QuickFileReportsService()
    from datetime import datetime, timezone

    stored = QuickFileReportsResponse(synced_at=datetime.now(timezone.utc).isoformat())

    async def fake_stored(_db):
        return stored

    monkeypatch.setattr(service, "get_stored_reports", fake_stored)
    assert await service.get_or_refresh_reports(object()) is stored


@pytest.mark.asyncio
async def test_get_or_refresh_skips_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = QuickFileReportsService()
    called = {"sync": False}

    async def fake_stored(_db):
        return None

    async def fake_sync(_db, _config):
        called["sync"] = True
        return QuickFileReportsResponse(synced_at="live")

    async def fake_status(_db):
        return SimpleNamespace(configured=False)

    monkeypatch.setattr(service, "get_stored_reports", fake_stored)
    monkeypatch.setattr(service, "sync_reports", fake_sync)
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_settings_service.get_status",
        fake_status,
    )
    assert await service.get_or_refresh_reports(object()) is None
    assert called["sync"] is False


@pytest.mark.asyncio
async def test_get_or_refresh_pulls_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = QuickFileReportsService()
    live = QuickFileReportsResponse(synced_at="live")

    async def fake_stored(_db):
        return None

    async def fake_config(_db):
        return QuickFileConfig(account_number="1", api_key="k", application_id="a")

    async def fake_sync(_db, _config):
        return live

    async def fake_status(_db):
        return SimpleNamespace(configured=True)

    monkeypatch.setattr(service, "get_stored_reports", fake_stored)
    monkeypatch.setattr(service, "sync_reports", fake_sync)
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_settings_service.get_status",
        fake_status,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_settings_service.get_config",
        fake_config,
    )
    assert await service.get_or_refresh_reports(object()) is live


@pytest.mark.asyncio
async def test_get_or_refresh_replaces_stale_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = QuickFileReportsService()
    stored = QuickFileReportsResponse(synced_at="2020-01-01T00:00:00+00:00")
    live = QuickFileReportsResponse(synced_at="live")

    async def fake_stored(_db):
        return stored

    async def fake_config(_db):
        return QuickFileConfig(account_number="1", api_key="k", application_id="a")

    async def fake_sync(_db, _config):
        return live

    async def fake_status(_db):
        return SimpleNamespace(configured=True)

    monkeypatch.setattr(service, "get_stored_reports", fake_stored)
    monkeypatch.setattr(service, "sync_reports", fake_sync)
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_settings_service.get_status",
        fake_status,
    )
    monkeypatch.setattr(
        "app.services.finance.quickfile_reports_service.quickfile_settings_service.get_config",
        fake_config,
    )
    assert await service.get_or_refresh_reports(object()) is live


@pytest.mark.asyncio
async def test_get_stored_reports_rehoms_live_misfiled_2100_2300() -> None:
    """Reports page reads stored JSON; normalize must fix 2100/2300 without a re-sync."""
    service = QuickFileReportsService()
    payload = {
        "synced_at": "2026-08-19T12:00:00+00:00",
        "profit_and_loss_month": None,
        "profit_and_loss_ytd": None,
        "balance_sheet": {
            "to_date": "2026-08-19",
            "fixed_assets_gbp": 0.0,
            "current_assets_gbp": 37770.47,
            "current_liabilities_gbp": 45662.43,
            "long_term_liabilities_gbp": 0.0,
            "capital_and_reserves_gbp": 0.0,
            "debtors_gbp": 0.0,
            "creditors_gbp": 0.0,
            "vat_reserve_gbp": 0.0,
            "vat_liability_gbp": 0.0,
            "sections": [
                {
                    "key": "CurrentAssets",
                    "label": "Current assets",
                    "lines": [
                        {
                            "nominal_code": "1200",
                            "label": "Debtors Control Account",
                            "amount_gbp": 8572.2,
                        },
                        {
                            "nominal_code": "2100",
                            "label": "Creditors Control Account",
                            "amount_gbp": 2342.43,
                        },
                        {
                            "nominal_code": "2300",
                            "label": "Loans",
                            "amount_gbp": 26855.84,
                        },
                    ],
                    "subtotal_gbp": 37770.47,
                },
                {
                    "key": "CurrentLiabilities",
                    "label": "Creditors: amounts falling due within one year",
                    "lines": [
                        {"nominal_code": "2200", "label": "VAT", "amount_gbp": 45662.43}
                    ],
                    "subtotal_gbp": 45662.43,
                },
                {
                    "key": "LongTermLiabilities",
                    "label": "Creditors: amounts falling due after one year",
                    "lines": [],
                    "subtotal_gbp": 0.0,
                },
            ],
        },
    }

    class _Row:
        value = json.dumps(payload)

    class _Db:
        async def scalar(self, _stmt):
            return _Row()

    reports = await service.get_stored_reports(_Db())
    assert reports is not None
    assert reports.balance_sheet is not None
    bs = reports.balance_sheet
    by_key = {section.key: section for section in bs.sections}
    asset_codes = [line.nominal_code for line in by_key["CurrentAssets"].lines]
    assert asset_codes == ["1200"]
    assert "2100" not in asset_codes
    assert "2300" not in asset_codes
    assert bs.current_assets_gbp == pytest.approx(8572.2)
    assert any(line.nominal_code == "2100" for line in by_key["CurrentLiabilities"].lines)
    assert any(line.nominal_code == "2300" for line in by_key["LongTermLiabilities"].lines)
    assert bs.long_term_liabilities_gbp == 26855.84
    assert bs.creditors_gbp == 2342.43
