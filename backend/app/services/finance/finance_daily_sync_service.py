"""Daily refresh of live finance connections that are already configured."""

from __future__ import annotations

import logging

from app.db.session import SessionLocal
from app.integrations.base import IntegrationNotConfiguredError
from app.schemas.finance import FinanceDailySyncResult
from app.services.finance.lunchflow_sync_service import lunchflow_sync_service
from app.services.finance.quickfile_sync_service import quickfile_sync_service
from app.services.lunchflow_settings_service import lunchflow_settings_service
from app.services.quickfile_settings_service import quickfile_settings_service

logger = logging.getLogger(__name__)


class FinanceDailySyncService:
    async def sync_once(self) -> FinanceDailySyncResult:
        result = FinanceDailySyncResult()
        async with SessionLocal() as db:
            if quickfile_settings_service.env_configured():
                try:
                    config = await quickfile_settings_service.get_config(db)
                    # Once-only ~2-year walk when stored lookback is missing/short.
                    # After mark_full_history_imported(730), stay on ~90-day incremental.
                    # Live dashboard refresh never reaches this service.
                    if await quickfile_settings_service.needs_deep_history_extension(db):
                        if await quickfile_settings_service.is_quota_blocked(db):
                            status = await quickfile_settings_service.get_status(db)
                            result.quickfile = (
                                "QuickFile API quota exhausted — retry after midnight UTC. "
                                f"Last error: {status.last_error or 'API request limit exceeded'}"
                            )
                        else:
                            synced = await quickfile_sync_service.sync(
                                db, config, force_full=True
                            )
                            result.quickfile = synced.message
                    else:
                        synced = await quickfile_sync_service.sync(
                            db, config, incremental_only=True
                        )
                        result.quickfile = synced.message
                except IntegrationNotConfiguredError as exc:
                    result.quickfile = str(exc)
                except Exception as exc:
                    result.ok = False
                    result.quickfile = "QuickFile daily sync failed"
                    logger.warning("QuickFile daily sync failed: %s", exc)
                    try:
                        await quickfile_settings_service.record_error(db, str(exc))
                    except Exception:
                        logger.warning(
                            "Could not persist QuickFile daily sync error",
                            exc_info=True,
                        )
            else:
                result.quickfile = "QuickFile not configured — skipped"

            if lunchflow_settings_service.env_configured():
                try:
                    config = await lunchflow_settings_service.get_config(db)
                    synced = await lunchflow_sync_service.sync(db, config)
                    result.lunchflow = synced.message
                except IntegrationNotConfiguredError as exc:
                    result.lunchflow = str(exc)
                except Exception as exc:
                    result.ok = False
                    result.lunchflow = "Lunch Flow daily sync failed"
                    logger.warning("Lunch Flow daily sync failed: %s", exc)
            else:
                result.lunchflow = "Lunch Flow not configured — skipped"

            try:
                from app.services.finance.finance_transfer_service import (
                    finance_transfer_service,
                )

                unmarked = await finance_transfer_service.unmark_false_transfers(
                    db, persist=True, redetect=True
                )
                result.transfers = (
                    f"Cleared {unmarked.get('cleared', 0)} false transfer flag(s)"
                )
            except Exception as exc:
                result.transfers = "Transfer cleanup skipped"
                logger.warning("Daily transfer cleanup failed: %s", exc)

            try:
                from app.services.finance.finance_backup_service import create_backup

                backup = await create_backup(db, trigger="daily_sync")
                result.backup = str(backup.get("location") or "ok")
            except Exception as exc:
                result.backup = "Backup skipped"
                logger.warning("Daily finance backup skipped: %s", exc)
        return result


finance_daily_sync_service = FinanceDailySyncService()
