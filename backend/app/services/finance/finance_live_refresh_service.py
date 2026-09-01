"""Refresh configured live connections so dashboards do not show stale zeros."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.quickfile_client import QuickFileError
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.lunchflow_sync_service import lunchflow_sync_service
from app.services.finance.quickfile_sync_service import quickfile_sync_service
from app.services.lunchflow_settings_service import lunchflow_settings_service
from app.services.quickfile_settings_service import (
    is_quickfile_quota_error,
    quickfile_settings_service,
)

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
        """Update live balances (and optionally Lunch Flow transactions) when stale.

        Dashboard background refresh uses balances only so pages stay fast and
        QuickFile never runs Bank_Search history from a dashboard hit.
        Full QuickFile transaction import is reserved for explicit Sync / daily cron.
        """
        # Same AsyncSession cannot be used concurrently — keep these sequential
        # but each path is balances-only so the whole call stays short.
        await self._refresh_quickfile(db)
        await self._refresh_lunchflow(db, include_transactions=include_transactions)
        # Heal salary / cross-scope false transfer marks so Money in recovers
        # without waiting for a manual Detect transfers click.
        try:
            from app.services.finance.finance_transfer_service import (
                finance_transfer_service,
            )

            await finance_transfer_service.unmark_false_transfers(
                db, persist=True, redetect=True
            )
        except Exception:
            logger.warning("Could not clear false transfer marks", exc_info=True)
            await db.rollback()
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
        if await quickfile_settings_service.is_quota_blocked(db):
            logger.info(
                "Skipping live QuickFile balance refresh — API quota exhausted until midnight UTC"
            )
            return
        try:
            config = await quickfile_settings_service.get_config(db)
            # Balances + debtors only. Never full sync() / Bank_Search history.
            await quickfile_sync_service.sync_balances(
                db, config, include_reports=False
            )
        except QuickFileError as exc:
            await quickfile_settings_service.record_error(db, str(exc))
            logger.warning(
                "Live QuickFile balance refresh failed%s",
                " (quota)" if is_quickfile_quota_error(exc) else "",
                exc_info=True,
            )
        except Exception as exc:
            await quickfile_settings_service.record_error(db, str(exc))
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


finance_live_refresh_service = FinanceLiveRefreshService()
