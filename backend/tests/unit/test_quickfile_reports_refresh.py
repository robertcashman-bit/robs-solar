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
async def test_get_stored_reports_keeps_live_2100_2300_as_assets() -> None:
    """Reports page keeps debit 2100/2300 in Current assets; official totals stay."""
    service = QuickFileReportsService()
    payload = {
        "synced_at": "2026-09-01T12:00:00+00:00",
        "profit_and_loss_month": None,
        "profit_and_loss_ytd": None,
        "balance_sheet": {
            "to_date": "2026-09-01",
            "fixed_assets_gbp": 37183.24,
            "current_assets_gbp": 38190.14,
            "current_liabilities_gbp": 45335.82,
            "long_term_liabilities_gbp": 0.0,
            "capital_and_reserves_gbp": 30037.56,
            "debtors_gbp": 7597.31,
            "creditors_gbp": 0.0,
            "vat_reserve_gbp": 0.47,
            "vat_liability_gbp": 3070.93,
            "sections": [
                {
                    "key": "CurrentAssets",
                    "label": "Current assets",
                    "lines": [
                        {
                            "nominal_code": "1200",
                            "label": "Debtors Control Account",
                            "amount_gbp": 7597.31,
                        },
                        {
                            "nominal_code": "2100",
                            "label": "Creditors Control Account",
                            "amount_gbp": 2391.83,
                        },
                        {
                            "nominal_code": "2300",
                            "label": "Loans",
                            "amount_gbp": 27720.15,
                        },
                    ],
                    "subtotal_gbp": 38190.14,
                },
                {
                    "key": "CurrentLiabilities",
                    "label": "Creditors: amounts falling due within one year",
                    "lines": [
                        {"nominal_code": "50", "label": "HP Finance", "amount_gbp": 15642.94},
                        {"nominal_code": "2200", "label": "VAT", "amount_gbp": 3070.93},
                    ],
                    "subtotal_gbp": 45335.82,
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
    assert "2100" in asset_codes
    assert "2300" in asset_codes
    assert bs.current_assets_gbp == 38190.14
    assert bs.long_term_liabilities_gbp == 0.0
    assert bs.capital_and_reserves_gbp == 30037.56
    assert not any(
        line.nominal_code == "2300" for line in by_key["LongTermLiabilities"].lines
    )


@pytest.mark.asyncio
async def test_get_stored_reports_restores_official_ca_subtotal() -> None:
    """Reports CA label uses official QF total, not the remaining-line sum after 2204/2201 move."""
    service = QuickFileReportsService()
    payload = {
        "synced_at": "2026-09-23T12:00:00+00:00",
        "profit_and_loss_month": None,
        "profit_and_loss_ytd": None,
        "balance_sheet": {
            "to_date": "2026-09-23",
            "fixed_assets_gbp": 38119.54,
            "current_assets_gbp": 10041.01,
            "current_liabilities_gbp": 43768.02,
            "long_term_liabilities_gbp": 9675.10,
            "capital_and_reserves_gbp": -5282.57,
            "debtors_gbp": 8214.60,
            "creditors_gbp": 1495.40,
            "vat_reserve_gbp": 0.47,
            "vat_liability_gbp": 623.37,
            "sections": [
                {
                    "key": "CurrentAssets",
                    "label": "Current assets",
                    "lines": [
                        {
                            "nominal_code": "1100",
                            "label": "Debtors Control Account",
                            "amount_gbp": 8214.60,
                        },
                        {
                            "nominal_code": "1200",
                            "label": "Current Account",
                            "amount_gbp": 0.11,
                        },
                        {"nominal_code": "1210", "label": "VAT Account", "amount_gbp": 0.47},
                        {
                            "nominal_code": "2100",
                            "label": "Creditors Control Account",
                            "amount_gbp": 1495.40,
                        },
                    ],
                    "subtotal_gbp": 9710.58,
                },
                {
                    "key": "CurrentLiabilities",
                    "label": "Creditors: amounts falling due within one year",
                    "lines": [
                        {"nominal_code": "50", "label": "HP Finance", "amount_gbp": 9192.00},
                        {
                            "nominal_code": "2204",
                            "label": "Manual Adjustments",
                            "amount_gbp": 330.27,
                        },
                        {
                            "nominal_code": "2201",
                            "label": "Purchase Tax Control Account",
                            "amount_gbp": 0.16,
                        },
                    ],
                    "subtotal_gbp": 44098.45,
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
    assert bs.current_assets_gbp == 10041.01
    assert by_key["CurrentAssets"].subtotal_gbp == 10041.01
    assert by_key["CurrentLiabilities"].subtotal_gbp == 43768.02
    assert any(line.nominal_code == "2204" for line in by_key["CurrentLiabilities"].lines)
    assert any(line.nominal_code == "2201" for line in by_key["CurrentLiabilities"].lines)


def test_year_start_is_calendar_first_january() -> None:
    """YTD P&L FromDate is 1 Jan of the UTC calendar year — DLS FY also ends 31 Dec."""
    from datetime import datetime, timezone

    from app.services.finance.quickfile_reports_service import _year_start

    as_of = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    assert _year_start(as_of) == "2026-01-01"


@pytest.mark.asyncio
async def test_fetch_live_reports_requests_calendar_ytd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stored YTD dates are the window we asked QF for (1 Jan–today), not last FY."""
    from datetime import datetime, timezone

    from app.services.finance import quickfile_reports_service as svc_mod

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 23, 15, 0, tzinfo=tz or timezone.utc)

    captured: list[tuple[str | None, str | None]] = []

    class _Client:
        def __init__(self, _config) -> None:
            pass

        async def fetch_profit_and_loss(self, *, from_date=None, to_date=None):
            captured.append((from_date, to_date))
            return {
                "Totals": {
                    "Turnover": 59841.54,
                    "LessCostofSales": 0,
                    "LessExpenses": 0,
                    "NetProfit": 28361.47,
                }
            }

        async def fetch_balance_sheet(self, *, to_date=None, show_as_nbv=False):
            return {
                "Totals": {
                    "FixedAssets": 0,
                    "CurrentAssets": 0,
                    "CurrentLiabilities": 0,
                    "LongTermLiabilities": 0,
                    "CapitalAndReserves": 0,
                }
            }

    monkeypatch.setattr(svc_mod, "datetime", _Frozen)
    monkeypatch.setattr(svc_mod, "QuickFileClient", _Client)
    service = QuickFileReportsService()
    reports = await service.fetch_live_reports(
        QuickFileConfig(account_number="1", api_key="k", application_id="a")
    )
    assert captured == [("2026-09-01", "2026-09-23"), ("2026-01-01", "2026-09-23")]
    assert reports.profit_and_loss_ytd is not None
    assert reports.profit_and_loss_ytd.from_date == "2026-01-01"
    assert reports.profit_and_loss_ytd.to_date == "2026-09-23"
    assert reports.profit_and_loss_ytd.turnover_gbp == 59841.54
