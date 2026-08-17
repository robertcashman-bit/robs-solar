"""Tesla credential storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.finance import TeslaConfig, TeslaConfigStatus

_CONFIG_KEY = "tesla"
_LAST_SYNC_KEY = "tesla_last_sync_at"


class TeslaSettingsService:
    def _env_config(self) -> TeslaConfig:
        return TeslaConfig(
            client_id=settings.tesla_client_id,
            client_secret=settings.tesla_client_secret,
            refresh_token=settings.tesla_refresh_token,
            energy_site_id=settings.tesla_energy_site_id,
        )

    async def _get_row(self, db: AsyncSession, key: str) -> AppSettingRow | None:
        return await db.scalar(select(AppSettingRow).where(AppSettingRow.key == key))

    async def get_config(self, db: AsyncSession) -> TeslaConfig:
        row = await self._get_row(db, _CONFIG_KEY)
        if row is None:
            return self._env_config()
        stored = TeslaConfig.model_validate(json.loads(row.value))
        env = self._env_config()
        return TeslaConfig(
            client_id=stored.client_id or env.client_id,
            client_secret=stored.client_secret or env.client_secret,
            refresh_token=stored.refresh_token or env.refresh_token,
            energy_site_id=stored.energy_site_id or env.energy_site_id,
        )

    async def get_status(self, db: AsyncSession) -> TeslaConfigStatus:
        config = await self.get_config(db)
        sync_row = await self._get_row(db, _LAST_SYNC_KEY)
        configured = bool(config.client_id and config.client_secret and config.refresh_token)
        return TeslaConfigStatus(
            client_id=config.client_id,
            client_secret_set=bool(config.client_secret),
            refresh_token_set=bool(config.refresh_token),
            energy_site_id=config.energy_site_id,
            configured=configured,
            connected=configured,
            last_sync_at=sync_row.value if sync_row else None,
        )

    async def set_config(self, db: AsyncSession, config: TeslaConfig) -> TeslaConfigStatus:
        current = await self.get_config(db)
        if not config.client_secret:
            config.client_secret = current.client_secret
        if not config.refresh_token:
            config.refresh_token = current.refresh_token
        row = await self._get_row(db, _CONFIG_KEY)
        payload = json.dumps(config.model_dump())
        if row is None:
            db.add(AppSettingRow(key=_CONFIG_KEY, value=payload))
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


tesla_settings_service = TeslaSettingsService()
