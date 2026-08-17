"""Refresh configured live connections so dashboards do not show stale zeros."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.lunchflow_sync_service import lunchflow_sync_service
from app.services.finance.quickfile_sync_service import quickfile_sync_service
from app.services.lunchflow_settings_service import lunchflow_settings_service
from app.services.quickfile_settings_service import quickfile_settings_service

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=15)


def is_stale(timestamp: str | None, *, max_age: timedelta = STALE_AFTER) -> bool:
    if not timestamp:
        return True
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - parsed > max_age


class FinanceLiveRefreshService:
    async def ensure_fresh(
        self,
        db: AsyncSession,
        *,
        include_transactions: bool = False,
    ) -> None:
        """Update live balances (and optionally transactions) when stale.

        Dashboard background refresh uses balances only so pages stay fast.
        Full transaction import is reserved for explicit Refresh / Connect sync.
        """
        # Same AsyncSession cannot be used concurrently — keep these sequential
        # but each path is balances-only so the whole call stays short.
        await self._refresh_quickfile(db)
        await self._refresh_lunchflow(db, include_transactions=include_transactions)
        await self._refresh_quickfile_reports(db)
        try:
            await finance_liabilities_service.ensure_from_accounts(db)
            await db.commit()
        except Exception:
            logger.warning("Could not mirror live accounts onto debts", exc_info=True)
            await db.rollback()
        try:
            from app.services.finance.finance_budget_plan_service import (
                finance_budget_plan_service,
            )

            await finance_budget_plan_service.ensure_active_from_suggestion(db)
        except Exception:
            logger.warning("Could not create recommended budget from live data", exc_info=True)
            await db.rollback()

    async def _refresh_quickfile(self, db: AsyncSession) -> None:
        status = await quickfile_settings_service.get_status(db)
        if not status.configured:
            return
        if not is_stale(status.last_sync_at):
            return
        try:
            config = await quickfile_settings_service.get_config(db)
            await quickfile_sync_service.sync(
                db, config, include_reports=False, backup=False
            )
        except Exception:
            logger.warning("Live QuickFile account refresh failed", exc_info=True)

    async def _refresh_lunchflow(
        self, db: AsyncSession, *, include_transactions: bool
    ) -> None:
        status = await lunchflow_settings_service.get_status(db)
        if not status.configured:
            return
        if not is_stale(status.last_sync_at):
            return
        try:
            config = await lunchflow_settings_service.get_config(db)
            if include_transactions:
                await lunchflow_sync_service.sync(db, config)
            else:
                await lunchflow_sync_service.sync_balances(db, config)
        except Exception:
            logger.warning("Live Lunch Flow account refresh failed", exc_info=True)

    async def _refresh_quickfile_reports(self, db: AsyncSession) -> None:
        status = await quickfile_settings_service.get_status(db)
        if not status.configured:
            return
        try:
            from app.services.finance.quickfile_reports_service import (
                quickfile_reports_service,
            )

            await quickfile_reports_service.get_or_refresh_reports(db)
        except Exception:
            logger.warning("Live QuickFile report refresh failed", exc_info=True)


finance_live_refresh_service = FinanceLiveRefreshService()
