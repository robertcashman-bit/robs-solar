"""Lunch Flow API key settings — env seed with optional DB override."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.finance import LunchFlowConfig, LunchFlowConfigStatus

_LUNCH_FLOW_KEY = "lunch_flow"
_LAST_SYNC_KEY = "lunch_flow_last_sync_at"


class LunchFlowSettingsService:
    def _env_config(self) -> LunchFlowConfig:
        return LunchFlowConfig(api_key=settings.lunch_flow_api_key)

    async def _get_row(self, db: AsyncSession, key: str) -> AppSettingRow | None:
        return await db.scalar(select(AppSettingRow).where(AppSettingRow.key == key))

    async def get_config(self, db: AsyncSession) -> LunchFlowConfig:
        row = await self._get_row(db, _LUNCH_FLOW_KEY)
        if row is None:
            return self._env_config()
        stored = LunchFlowConfig.model_validate(json.loads(row.value))
        env = self._env_config()
        return LunchFlowConfig(api_key=stored.api_key or env.api_key)

    async def get_status(self, db: AsyncSession) -> LunchFlowConfigStatus:
        config = await self.get_config(db)
        sync_row = await self._get_row(db, _LAST_SYNC_KEY)
        last_sync = sync_row.value if sync_row else None
        configured = bool(config.api_key)
        return LunchFlowConfigStatus(
            api_key_set=configured,
            configured=configured,
            last_sync_at=last_sync,
        )

    async def set_config(self, db: AsyncSession, config: LunchFlowConfig) -> LunchFlowConfigStatus:
        current = await self.get_config(db)
        if not config.api_key:
            config.api_key = current.api_key
        row = await self._get_row(db, _LUNCH_FLOW_KEY)
        payload = json.dumps(config.model_dump())
        if row is None:
            db.add(AppSettingRow(key=_LUNCH_FLOW_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()
        return await self.get_status(db)

    async def mark_synced(self, db: AsyncSession) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row = await self._get_row(db, _LAST_SYNC_KEY)
        if row is None:
            db.add(AppSettingRow(key=_LAST_SYNC_KEY, value=now))
        else:
            row.value = now
        await db.commit()


lunch_flow_settings_service = LunchFlowSettingsService()
