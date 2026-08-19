"""Fetch and persist QuickFile P&L and balance sheet reports."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSettingRow, BusinessFinanceSnapshotRow
from app.integrations.quickfile_client import QuickFileClient, QuickFileError
from app.integrations.quickfile_reports import (
    normalize_parsed_balance_sheet,
    parse_balance_sheet,
    parse_profit_and_loss,
)
from app.schemas.finance import (
    QuickFileBalanceSheetSummary,
    QuickFileConfig,
    QuickFileProfitAndLossSummary,
    QuickFileReportsResponse,
)
from app.services.quickfile_settings_service import quickfile_settings_service

logger = logging.getLogger(__name__)

_REPORTS_KEY = "quickfile_reports"


def _month_start(today: datetime) -> str:
    return today.date().replace(day=1).isoformat()


def _year_start(today: datetime) -> str:
    return today.date().replace(month=1, day=1).isoformat()


def _normalize_reports_payload(payload: dict) -> dict:
    """Fix misfiled 2xxx lines on stored reports without requiring a re-sync."""
    balance_sheet = payload.get("balance_sheet")
    if isinstance(balance_sheet, dict) and balance_sheet.get("sections"):
        payload["balance_sheet"] = normalize_parsed_balance_sheet(balance_sheet)
    return payload


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
            payload = _normalize_reports_payload(json.loads(row.value))
            return QuickFileReportsResponse.model_validate(payload)
        except (json.JSONDecodeError, ValueError):
            return None

    async def get_or_refresh_reports(
        self, db: AsyncSession
    ) -> QuickFileReportsResponse | None:
        from app.services.finance.finance_live_refresh_service import is_stale

        stored = await self.get_stored_reports(db)
        if stored is not None and not is_stale(stored.synced_at):
            return stored
        status = await quickfile_settings_service.get_status(db)
        if not status.configured:
            return stored
        config = await quickfile_settings_service.get_config(db)
        try:
            return await self.sync_reports(db, config)
        except Exception:
            logger.warning("Live QuickFile report refresh failed", exc_info=True)
            return stored

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
        except QuickFileError:
            raise
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
            .where(BusinessFinanceSnapshotRow.snapshot_date.startswith(month_key))
            .order_by(
                BusinessFinanceSnapshotRow.snapshot_date.desc(),
                BusinessFinanceSnapshotRow.created_at.desc(),
                BusinessFinanceSnapshotRow.id.desc(),
            )
            .limit(1)
        )
        debtors = bs.debtors_gbp if bs else 0.0
        creditors = bs.creditors_gbp if bs else 0.0
        # Cash in the VAT pot (current asset), never creditor-side VAT liability.
        vat_reserve = bs.vat_reserve_gbp if bs else 0.0
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
            db.add(
                BusinessFinanceSnapshotRow(
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
            )
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
