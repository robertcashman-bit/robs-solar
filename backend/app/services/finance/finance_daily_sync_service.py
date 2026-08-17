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
                    synced = await quickfile_sync_service.sync(db, config)
                    result.quickfile = synced.message
                except IntegrationNotConfiguredError as exc:
                    result.quickfile = str(exc)
                except Exception as exc:
                    result.ok = False
                    result.quickfile = "QuickFile daily sync failed"
                    logger.warning("QuickFile daily sync failed: %s", exc)
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
                from app.services.finance.finance_backup_service import create_backup

                backup = await create_backup(db, trigger="daily_sync")
                result.backup = str(backup.get("location") or "ok")
            except Exception as exc:
                result.backup = "Backup skipped"
                logger.warning("Daily finance backup skipped: %s", exc)
        return result


finance_daily_sync_service = FinanceDailySyncService()
