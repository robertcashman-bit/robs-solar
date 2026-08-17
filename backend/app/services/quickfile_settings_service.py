"""QuickFile credential settings — env seed with optional DB override."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.finance import (
    QuickFileConfig,
    QuickFileConfigStatus,
    integration_connection_state,
)
from app.services.settings_crypto import open_json, seal_json

_QUICKFILE_KEY = "quickfile"
_LAST_SYNC_KEY = "quickfile_last_sync_at"


class QuickFileSettingsService:
    def _env_config(self) -> QuickFileConfig:
        return QuickFileConfig(
            account_number=settings.quickfile_account_number,
            api_key=settings.quickfile_api_key,
            application_id=settings.quickfile_application_id,
        )

    @staticmethod
    def is_complete(config: QuickFileConfig) -> bool:
        return bool(config.account_number and config.api_key and config.application_id)

    async def _get_row(self, db: AsyncSession, key: str) -> AppSettingRow | None:
        return await db.scalar(select(AppSettingRow).where(AppSettingRow.key == key))

    async def _save_config(self, db: AsyncSession, config: QuickFileConfig) -> None:
        row = await self._get_row(db, _QUICKFILE_KEY)
        payload = seal_json(config.model_dump())
        if row is None:
            db.add(AppSettingRow(key=_QUICKFILE_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()

    async def get_config(self, db: AsyncSession) -> QuickFileConfig:
        row = await self._get_row(db, _QUICKFILE_KEY)
        if row is None:
            return self._env_config()
        stored = QuickFileConfig.model_validate(open_json(row.value))
        env = self._env_config()
        return QuickFileConfig(
            account_number=stored.account_number or env.account_number,
            api_key=stored.api_key or env.api_key,
            application_id=stored.application_id or env.application_id,
        )

    async def get_status(self, db: AsyncSession) -> QuickFileConfigStatus:
        config = await self.get_config(db)
        sync_row = await self._get_row(db, _LAST_SYNC_KEY)
        last_sync = sync_row.value if sync_row else None
        configured = self.is_complete(config)
        return QuickFileConfigStatus(
            account_number=config.account_number,
            api_key_set=bool(config.api_key),
            application_id=config.application_id,
            configured=configured,
            last_sync_at=last_sync,
            connection_state=integration_connection_state(configured, last_sync),
        )

    async def set_config(self, db: AsyncSession, config: QuickFileConfig) -> QuickFileConfigStatus:
        current = await self.get_config(db)
        if not config.api_key:
            config.api_key = current.api_key
        await self._save_config(db, config)
        return await self.get_status(db)

    async def seed_from_env(self, db: AsyncSession) -> bool:
        env = self._env_config()
        if not self.is_complete(env):
            return False
        current = await self.get_config(db)
        merged = QuickFileConfig(
            account_number=current.account_number or env.account_number,
            api_key=current.api_key or env.api_key,
            application_id=current.application_id or env.application_id,
        )
        if not self.is_complete(merged):
            return False
        row = await self._get_row(db, _QUICKFILE_KEY)
        if row is not None and self.is_complete(current):
            return False
        await self._save_config(db, merged)
        return True

    async def reconnect_from_env(self, db: AsyncSession) -> bool:
        env = self._env_config()
        if not self.is_complete(env):
            return False
        await self._save_config(db, env)
        return True

    async def mark_synced(self, db: AsyncSession) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row = await self._get_row(db, _LAST_SYNC_KEY)
        if row is None:
            db.add(AppSettingRow(key=_LAST_SYNC_KEY, value=now))
        else:
            row.value = now
        await db.commit()


quickfile_settings_service = QuickFileSettingsService()
