"""Notification settings — webhook, SMTP, and per-category toggles."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.domain import (
    NotificationCategoryToggle,
    NotificationSettings,
    NotificationSettingsStatus,
)

_KEY = "notification_settings"


class NotificationSettingsService:
    def _defaults(self) -> NotificationSettings:
        return NotificationSettings(
            webhook_url=settings.alert_webhook_url,
            smtp_port=587,
            export_price_threshold_pence=20.0,
            categories=NotificationCategoryToggle(),
        )

    async def get_settings(self, db: AsyncSession) -> NotificationSettings:
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _KEY))
        if row is None:
            return self._defaults()
        return NotificationSettings.model_validate(json.loads(row.value))

    async def get_status(self, db: AsyncSession) -> NotificationSettingsStatus:
        config = await self.get_settings(db)
        return NotificationSettingsStatus(
            webhook_url_set=bool(config.webhook_url),
            smtp_configured=bool(config.smtp_host and config.email_to),
            email_to=config.email_to,
            export_price_threshold_pence=config.export_price_threshold_pence,
            categories=config.categories,
        )

    async def set_settings(
        self, db: AsyncSession, incoming: NotificationSettings
    ) -> NotificationSettingsStatus:
        current = await self.get_settings(db)
        if not incoming.smtp_password:
            incoming.smtp_password = current.smtp_password
        payload = json.dumps(incoming.model_dump())
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _KEY))
        if row is None:
            db.add(AppSettingRow(key=_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()
        return await self.get_status(db)

    def category_enabled(
        self, config: NotificationSettings, category: str
    ) -> bool:
        toggles = config.categories.model_dump()
        return bool(toggles.get(category, True))


notification_settings_service = NotificationSettingsService()
