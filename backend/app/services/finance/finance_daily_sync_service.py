"""Background daily finance sync — Open Banking and QuickFile when configured."""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.db.session import SessionLocal
from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.enable_banking_client import EnableBankingClient, EnableBankingError
from app.schemas.finance import FinanceDailySyncResult
from app.services.finance.open_banking_sync_service import open_banking_sync_service
from app.services.finance.quickfile_sync_service import quickfile_sync_service
from app.services.open_banking_settings_service import open_banking_settings_service
from app.services.quickfile_settings_service import quickfile_settings_service

logger = logging.getLogger(__name__)

_sync_task: asyncio.Task | None = None


async def _mark_expired_sessions(db) -> None:
    """Mark Open Banking sessions that no longer authorise as EXPIRED."""
    config = await open_banking_settings_service.get_config(db)
    if not open_banking_settings_service.is_configured(config):
        return
    if config.provider != "enable_banking":
        return

    client = EnableBankingClient(config)
    requisitions = await open_banking_settings_service.list_requisitions(db)
    changed = False
    for req in requisitions:
        if req.status != "AUTHORIZED" or not req.id:
            continue
        try:
            await client.get_session(req.id)
        except EnableBankingError as exc:
            message = str(exc).lower()
            if any(
                token in message for token in ("401", "403", "expired", "unauthorized", "forbidden")
            ):
                req.status = "EXPIRED"
                changed = True
                logger.info("Open Banking consent expired for %s", req.institution_name)
    if changed:
        await open_banking_settings_service.save_requisitions(db, requisitions)


async def sync_once() -> FinanceDailySyncResult:
    result = FinanceDailySyncResult()
    async with SessionLocal() as db:
        await _mark_expired_sessions(db)

        ob_config = await open_banking_settings_service.get_config(db)
        if open_banking_settings_service.is_configured(ob_config):
            try:
                sync_result = await open_banking_sync_service.sync(db, ob_config)
                result.open_banking = sync_result.message
                logger.info("Finance daily sync (Open Banking): %s", sync_result.message)
            except IntegrationNotConfiguredError as exc:
                result.open_banking = str(exc)
                logger.debug("Open Banking daily sync skipped: %s", exc)
            except Exception as exc:
                result.open_banking = "Daily sync failed"
                result.ok = False
                logger.warning("Open Banking daily sync failed: %s", exc)
        else:
            result.open_banking = "Open Banking not configured — skipped"

        qf_config = await quickfile_settings_service.get_config(db)
        qf_status = await quickfile_settings_service.get_status(db)
        if qf_status.configured:
            try:
                sync_result = await quickfile_sync_service.sync(db, qf_config)
                result.quickfile = sync_result.message
                logger.info("Finance daily sync (QuickFile): %s", sync_result.message)
            except IntegrationNotConfiguredError as exc:
                result.quickfile = str(exc)
                logger.debug("QuickFile daily sync skipped: %s", exc)
            except Exception as exc:
                result.quickfile = "Daily sync failed"
                result.ok = False
                logger.warning("QuickFile daily sync failed: %s", exc)
        else:
            result.quickfile = "QuickFile not configured — skipped"

    return result


async def _sync_loop() -> None:
    interval_seconds = max(1, settings.finance_daily_sync_interval_hours) * 3600
    while True:
        await sync_once()
        await asyncio.sleep(interval_seconds)


def start_finance_daily_sync() -> asyncio.Task | None:
    global _sync_task
    if not settings.finance_daily_sync_enabled:
        return None
    # Serverless production uses Vercel Cron instead of an in-process loop.
    if settings.cron_secret.strip():
        logger.info("Finance daily sync: using external cron (CRON_SECRET set)")
        return None
    if _sync_task is not None and not _sync_task.done():
        return _sync_task
    _sync_task = asyncio.create_task(_sync_loop())
    return _sync_task


async def stop_finance_daily_sync() -> None:
    global _sync_task
    if _sync_task is not None:
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass
        _sync_task = None
