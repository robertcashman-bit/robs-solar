"""Fetch and persist QuickFile P&L and balance sheet reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSettingRow, BusinessFinanceSnapshotRow
from app.integrations.quickfile_client import QuickFileClient, QuickFileError
from app.integrations.quickfile_reports import parse_balance_sheet, parse_profit_and_loss
from app.schemas.finance import (
    QuickFileBalanceSheetSummary,
    QuickFileConfig,
    QuickFileProfitAndLossSummary,
    QuickFileReportsResponse,
)

_REPORTS_KEY = "quickfile_reports"


def _month_start(today: datetime) -> str:
    return today.date().replace(day=1).isoformat()


def _year_start(today: datetime) -> str:
    return today.date().replace(month=1, day=1).isoformat()


class QuickFileReportsService:
    async def fetch_live_reports(self, config: QuickFileConfig) -> QuickFileReportsResponse:
        client = QuickFileClient(config)
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        month_start = _month_start(now)
        year_start = _year_start(now)

        pl_month_body = await client.fetch_profit_and_loss(from_date=month_start, to_date=today)
        pl_ytd_body = await client.fetch_profit_and_loss(from_date=year_start, to_date=today)
        bs_body = await client.fetch_balance_sheet(to_date=today)

        synced_at = now.isoformat()
        return QuickFileReportsResponse(
            synced_at=synced_at,
            profit_and_loss_month=QuickFileProfitAndLossSummary.model_validate(
                parse_profit_and_loss(pl_month_body, from_date=month_start, to_date=today)
            ),
            profit_and_loss_ytd=QuickFileProfitAndLossSummary.model_validate(
                parse_profit_and_loss(pl_ytd_body, from_date=year_start, to_date=today)
            ),
            balance_sheet=QuickFileBalanceSheetSummary.model_validate(
                parse_balance_sheet(bs_body, to_date=today)
            ),
        )

    async def get_stored_reports(self, db: AsyncSession) -> QuickFileReportsResponse | None:
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _REPORTS_KEY))
        if row is None:
            return None
        try:
            return QuickFileReportsResponse.model_validate(json.loads(row.value))
        except (json.JSONDecodeError, ValueError):
            return None

    async def save_reports(
        self, db: AsyncSession, reports: QuickFileReportsResponse
    ) -> QuickFileReportsResponse:
        payload = reports.model_dump(mode="json")
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _REPORTS_KEY))
        encoded = json.dumps(payload)
        if row is None:
            db.add(AppSettingRow(key=_REPORTS_KEY, value=encoded))
        else:
            row.value = encoded
        await db.commit()
        return reports

    async def sync_reports(
        self, db: AsyncSession, config: QuickFileConfig
    ) -> QuickFileReportsResponse:
        try:
            reports = await self.fetch_live_reports(config)
        except QuickFileError as exc:
            raise exc
        await self.save_reports(db, reports)
        await self._upsert_business_snapshot(db, reports)
        return reports

    async def _upsert_business_snapshot(
        self,
        db: AsyncSession,
        reports: QuickFileReportsResponse,
    ) -> None:
        pl = reports.profit_and_loss_month
        bs = reports.balance_sheet
        if pl is None:
            return

        month_key = pl.to_date[:7]
        row = await db.scalar(
            select(BusinessFinanceSnapshotRow)
            .where(BusinessFinanceSnapshotRow.snapshot_date == month_key)
            .limit(1)
        )
        debtors = bs.debtors_gbp if bs else 0.0
        creditors = bs.creditors_gbp if bs else 0.0
        vat_reserve = bs.vat_liability_gbp if bs else 0.0
        profit = pl.net_profit_gbp
        cash_draw = max(0.0, profit - creditors)
        breakdown = {
            "source": "quickfile",
            "profit_and_loss_month": pl.model_dump(),
            "profit_and_loss_ytd": (
                reports.profit_and_loss_ytd.model_dump() if reports.profit_and_loss_ytd else None
            ),
            "balance_sheet": bs.model_dump() if bs else None,
        }
        now = datetime.now(timezone.utc)
        if row is None:
            row = BusinessFinanceSnapshotRow(
                snapshot_date=month_key,
                turnover_gbp=pl.turnover_gbp,
                expenses_gbp=pl.expenses_gbp,
                vat_reserve_gbp=vat_reserve,
                corp_tax_reserve_gbp=0.0,
                debtors_gbp=debtors,
                creditors_gbp=creditors,
                profit_estimate_gbp=profit,
                cash_available_to_draw_gbp=cash_draw,
                notes="Synced from QuickFile profit & loss and balance sheet",
                breakdown_json=json.dumps(breakdown),
                created_at=now,
            )
            db.add(row)
        else:
            row.turnover_gbp = pl.turnover_gbp
            row.expenses_gbp = pl.expenses_gbp
            row.vat_reserve_gbp = vat_reserve
            row.debtors_gbp = debtors
            row.creditors_gbp = creditors
            row.profit_estimate_gbp = profit
            row.cash_available_to_draw_gbp = cash_draw
            row.notes = "Synced from QuickFile profit & loss and balance sheet"
            row.breakdown_json = json.dumps(breakdown)
        await db.commit()


quickfile_reports_service = QuickFileReportsService()
