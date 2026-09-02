"""Refresh configured live connections so dashboards do not show stale zeros."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

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
        force_quickfile_reports: bool = False,
    ) -> dict[str, Any]:
        """Update live balances (and optionally Lunch Flow transactions) when stale.

        Dashboard background refresh uses balances only so pages stay fast and
        QuickFile never runs Bank_Search history from a dashboard hit.
        Full QuickFile transaction import is reserved for explicit Sync / daily cron.

        Explicit Overview Refresh / POST ``/live-refresh`` sets
        ``force_quickfile_reports=True`` so P&L + balance sheet are re-pulled
        every time, even when ``last_sync_at`` is still fresh.

        Returns a small status dict so callers can surface partial failures
        (balances OK, reports failed) without inventing figures.
        """
        status: dict[str, Any] = {
            "quickfile_reports_synced": False,
            "partial_failure": False,
            "warnings": [],
        }
        # Same AsyncSession cannot be used concurrently — keep these sequential
        # but each path is balances-only so the whole call stays short.
        qf = await self._refresh_quickfile(
            db, force_reports=force_quickfile_reports
        )
        status["quickfile_reports_synced"] = bool(qf.get("reports_synced"))
        if qf.get("warning"):
            status["partial_failure"] = True
            status["warnings"].append(str(qf["warning"]))
        lf = await self._refresh_lunchflow(db, include_transactions=include_transactions)
        if lf.get("warning"):
            status["partial_failure"] = True
            status["warnings"].append(str(lf["warning"]))
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
            status["partial_failure"] = True
            status["warnings"].append(
                "Could not clear false transfer marks — Money in may still miss salary."
            )
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
        return status

    async def _refresh_quickfile(
        self, db: AsyncSession, *, force_reports: bool = False
    ) -> dict[str, Any]:
        status = await quickfile_settings_service.get_status(db)
        if not status.configured:
            return {"reports_synced": False}
        # Background / balances-only: skip when a recent sync already ran.
        # Explicit live-refresh must always re-pull P&L + balance sheet.
        if not force_reports and not is_stale(status.last_sync_at):
            return {"reports_synced": False, "skipped": True}
        if await quickfile_settings_service.is_quota_blocked(db):
            logger.info(
                "Skipping live QuickFile balance refresh — API quota exhausted until midnight UTC"
            )
            return {
                "reports_synced": False,
                "warning": "QuickFile API quota exhausted — retry after midnight UTC.",
            }
        try:
            config = await quickfile_settings_service.get_config(db)
            # Balances + debtors only for history. Reports when forced / explicit.
            # Never full sync() / Bank_Search history.
            result = await quickfile_sync_service.sync_balances(
                db, config, include_reports=force_reports
            )
            reports_synced = bool(getattr(result, "reports_synced", False))
            if force_reports and not reports_synced:
                return {
                    "reports_synced": False,
                    "warning": (
                        "QuickFile balances updated, but the balance sheet "
                        "did not refresh — Defence Legal may show last saved figures."
                    ),
                }
            return {"reports_synced": reports_synced}
        except QuickFileError as exc:
            await quickfile_settings_service.record_error(db, str(exc))
            logger.warning(
                "Live QuickFile balance refresh failed%s",
                " (quota)" if is_quickfile_quota_error(exc) else "",
                exc_info=True,
            )
            return {
                "reports_synced": False,
                "warning": f"QuickFile refresh failed: {exc}",
            }
        except Exception as exc:
            await quickfile_settings_service.record_error(db, str(exc))
            logger.warning("Live QuickFile account refresh failed", exc_info=True)
            return {
                "reports_synced": False,
                "warning": f"QuickFile refresh failed: {exc}",
            }

    async def _refresh_lunchflow(
        self, db: AsyncSession, *, include_transactions: bool
    ) -> dict[str, Any]:
        status = await lunchflow_settings_service.get_status(db)
        if not status.configured:
            return {}
        if not is_stale(status.last_sync_at):
            return {"skipped": True}
        try:
            config = await lunchflow_settings_service.get_config(db)
            if include_transactions:
                await lunchflow_sync_service.sync(db, config)
            else:
                await lunchflow_sync_service.sync_balances(db, config)
            return {}
        except Exception as exc:
            logger.warning("Live Lunch Flow account refresh failed", exc_info=True)
            return {"warning": f"Lunch Flow refresh failed: {exc}"}


finance_live_refresh_service = FinanceLiveRefreshService()
