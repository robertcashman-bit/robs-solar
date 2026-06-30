"""Background loop that auto-aligns TOU bands to IOG cheap windows."""

from __future__ import annotations

import asyncio
import logging

from app.adapters.factory import get_adapter
from app.config import settings
from app.db.session import SessionLocal
from app.services.auto_schedule_service import auto_schedule_service

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


async def run_auto_schedule_once() -> None:
    try:
        async with SessionLocal() as db:
            adapter = get_adapter()
            await auto_schedule_service.run_once(db, adapter)
    except Exception as exc:
        logger.warning("Auto-scheduler run failed: %s", exc)


async def _scheduler_loop() -> None:
    interval = max(1, settings.auto_schedule_interval_minutes) * 60
    while True:
        await run_auto_schedule_once()
        await asyncio.sleep(interval)


def start_auto_scheduler() -> asyncio.Task | None:
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        return _scheduler_task
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    return _scheduler_task


async def stop_auto_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
