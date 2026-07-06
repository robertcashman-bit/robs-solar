"""Runtime safety overrides for read-only and live-write flags."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.domain import SafetySettings, SafetySettingsUpdate

_KEY = "safety_settings"


class SafetySettingsService:
    _overrides: dict[str, bool] | None = None

    def _env_defaults(self) -> SafetySettings:
        return SafetySettings(
            read_only=settings.read_only,
            enable_live_writes=settings.enable_live_writes,
            runtime_overrides=False,
        )

    async def get_settings(self, db: AsyncSession) -> SafetySettings:
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _KEY))
        if row is None:
            return self._env_defaults()
        data = json.loads(row.value)
        self._overrides = data
        return SafetySettings(
            read_only=bool(data.get("read_only", settings.read_only)),
            enable_live_writes=bool(data.get("enable_live_writes", settings.enable_live_writes)),
            runtime_overrides=True,
        )

    async def update_settings(
        self, db: AsyncSession, update: SafetySettingsUpdate
    ) -> SafetySettings:
        current = await self.get_settings(db)
        payload = {
            "read_only": update.read_only if update.read_only is not None else current.read_only,
            "enable_live_writes": update.enable_live_writes
            if update.enable_live_writes is not None
            else current.enable_live_writes,
        }
        encoded = json.dumps(payload)
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _KEY))
        if row is None:
            db.add(AppSettingRow(key=_KEY, value=encoded))
        else:
            row.value = encoded
        await db.commit()
        self._overrides = payload
        return SafetySettings(
            read_only=payload["read_only"],
            enable_live_writes=payload["enable_live_writes"],
            runtime_overrides=True,
        )

    async def load_cache(self, db: AsyncSession) -> None:
        await self.get_settings(db)

    def effective_read_only(self) -> bool:
        if self._overrides is not None:
            return bool(self._overrides.get("read_only", settings.read_only))
        return settings.read_only

    def effective_enable_live_writes(self) -> bool:
        if self._overrides is not None:
            return bool(self._overrides.get("enable_live_writes", settings.enable_live_writes))
        return settings.enable_live_writes


safety_settings_service = SafetySettingsService()
