"""Octopus credential settings — stored in app_settings KV, seeded from env.

Persisting to the DB lets an admin configure Octopus from the Settings page
and have it apply live (via octopus_client.update_credentials) without editing
.env or restarting the backend.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.domain import OctopusConfig, OctopusConfigStatus
from app.services.octopus_client import OctopusCredentials, octopus_client

_OCTOPUS_KEY = "octopus"


class OctopusSettingsService:
    def _env_config(self) -> OctopusConfig:
        return OctopusConfig(
            api_key=settings.octopus_api_key,
            account_number=settings.octopus_account_number,
            mpan=settings.octopus_mpan,
            meter_serial=settings.octopus_meter_serial,
            region=(settings.octopus_region or "C").upper(),
        )

    async def get_config(self, db: AsyncSession) -> OctopusConfig:
        result = await db.execute(
            select(AppSettingRow).where(AppSettingRow.key == _OCTOPUS_KEY)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return self._env_config()
        return OctopusConfig.model_validate(json.loads(row.value))

    async def get_status(self, db: AsyncSession) -> OctopusConfigStatus:
        config = await self.get_config(db)
        return OctopusConfigStatus(
            api_key_set=bool(config.api_key),
            account_number=config.account_number,
            mpan=config.mpan,
            meter_serial=config.meter_serial,
            region=config.region,
            configured=bool(config.api_key),
        )

    async def set_config(self, db: AsyncSession, config: OctopusConfig) -> OctopusConfigStatus:
        # An empty api_key on update means "keep the existing key".
        if not config.api_key:
            current = await self.get_config(db)
            config.api_key = current.api_key
        config.region = (config.region or "C").upper()

        result = await db.execute(
            select(AppSettingRow).where(AppSettingRow.key == _OCTOPUS_KEY)
        )
        row = result.scalar_one_or_none()
        payload = json.dumps(config.model_dump())
        if row is None:
            db.add(AppSettingRow(key=_OCTOPUS_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()
        self._apply(config)
        return await self.get_status(db)

    async def load_into_client(self, db: AsyncSession) -> None:
        """Called on startup so DB-stored credentials override env defaults."""
        config = await self.get_config(db)
        if config.api_key:
            self._apply(config)

    def _apply(self, config: OctopusConfig) -> None:
        octopus_client.update_credentials(
            OctopusCredentials(
                api_key=config.api_key,
                account_number=config.account_number,
                mpan=config.mpan,
                meter_serial=config.meter_serial,
                region=config.region,
            )
        )


octopus_settings_service = OctopusSettingsService()
