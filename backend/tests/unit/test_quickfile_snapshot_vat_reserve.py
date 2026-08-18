"""QuickFile sync must write VAT pot cash into snapshot.vat_reserve_gbp."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.finance import (
    QuickFileBalanceSheetSummary,
    QuickFileProfitAndLossSummary,
    QuickFileReportsResponse,
)
from app.services.finance.quickfile_reports_service import QuickFileReportsService


@pytest.mark.asyncio
async def test_upsert_writes_vat_account_not_creditor_liability() -> None:
    service = QuickFileReportsService()
    reports = QuickFileReportsResponse(
        synced_at="2026-08-18T12:00:00+00:00",
        profit_and_loss_month=QuickFileProfitAndLossSummary(
            from_date="2026-08-01",
            to_date="2026-08-18",
            turnover_gbp=1000.0,
            cost_of_sales_gbp=0.0,
            expenses_gbp=200.0,
            net_profit_gbp=800.0,
        ),
        balance_sheet=QuickFileBalanceSheetSummary(
            to_date="2026-08-18",
            fixed_assets_gbp=0.0,
            current_assets_gbp=100.0,
            current_liabilities_gbp=2956.27,
            long_term_liabilities_gbp=0.0,
            capital_and_reserves_gbp=0.0,
            debtors_gbp=0.0,
            creditors_gbp=0.0,
            vat_reserve_gbp=0.47,
            vat_liability_gbp=2956.27,
        ),
    )

    added: list[object] = []
    db = MagicMock()
    db.scalar = AsyncMock(return_value=None)
    db.add = MagicMock(side_effect=lambda row: added.append(row))
    db.commit = AsyncMock()

    await service._upsert_business_snapshot(db, reports)

    assert len(added) == 1
    row = added[0]
    assert row.vat_reserve_gbp == 0.47
    assert row.vat_reserve_gbp != 2956.27


@pytest.mark.asyncio
async def test_upsert_updates_existing_row_with_vat_pot() -> None:
    service = QuickFileReportsService()
    existing = SimpleNamespace(
        turnover_gbp=0.0,
        expenses_gbp=0.0,
        vat_reserve_gbp=2956.27,
        debtors_gbp=0.0,
        creditors_gbp=0.0,
        profit_estimate_gbp=0.0,
        cash_available_to_draw_gbp=0.0,
        notes="",
        breakdown_json="",
    )
    reports = QuickFileReportsResponse(
        synced_at="2026-08-18T12:00:00+00:00",
        profit_and_loss_month=QuickFileProfitAndLossSummary(
            from_date="2026-08-01",
            to_date="2026-08-18",
            turnover_gbp=1000.0,
            cost_of_sales_gbp=0.0,
            expenses_gbp=200.0,
            net_profit_gbp=800.0,
        ),
        balance_sheet=QuickFileBalanceSheetSummary(
            to_date="2026-08-18",
            fixed_assets_gbp=0.0,
            current_assets_gbp=100.0,
            current_liabilities_gbp=2956.27,
            long_term_liabilities_gbp=0.0,
            capital_and_reserves_gbp=0.0,
            vat_reserve_gbp=0.47,
            vat_liability_gbp=2956.27,
        ),
    )

    db = MagicMock()
    db.scalar = AsyncMock(return_value=existing)
    db.commit = AsyncMock()

    await service._upsert_business_snapshot(db, reports)

    assert existing.vat_reserve_gbp == 0.47
