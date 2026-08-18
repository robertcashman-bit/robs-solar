"""QuickFile credential settings — env seed with optional DB override."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.finance import QuickFileConfig, QuickFileConfigStatus
from app.services.settings_crypto import open_json, seal_json

_QUICKFILE_KEY = "quickfile"
_LAST_SYNC_KEY = "quickfile_last_sync_at"
_FULL_IMPORT_KEY = "quickfile_full_import_at"
_BUDGET_ACCOUNTS_KEY = "quickfile_budget_account_ids"


class QuickFileSettingsService:
    def _env_config(self) -> QuickFileConfig:
        return QuickFileConfig(
            account_number=settings.quickfile_account_number,
            api_key=settings.quickfile_api_key,
            application_id=settings.quickfile_application_id,
        )

    def env_configured(self) -> bool:
        env = self._env_config()
        return bool(env.account_number and env.api_key and env.application_id)

    async def _get_row(self, db: AsyncSession, key: str) -> AppSettingRow | None:
        return await db.scalar(select(AppSettingRow).where(AppSettingRow.key == key))

    async def get_config(self, db: AsyncSession) -> QuickFileConfig:
        row = await self._get_row(db, _QUICKFILE_KEY)
        env = self._env_config()
        if row is None or not (row.value or "").strip():
            return env
        stored = QuickFileConfig.model_validate(open_json(row.value))
        return QuickFileConfig(
            account_number=stored.account_number or env.account_number,
            api_key=stored.api_key or env.api_key,
            application_id=stored.application_id or env.application_id,
        )

    async def get_budget_account_ids(self, db: AsyncSession) -> list[str]:
        row = await self._get_row(db, _BUDGET_ACCOUNTS_KEY)
        if row is None or not (row.value or "").strip():
            return []
        try:
            data = json.loads(row.value)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return [str(item) for item in data if str(item).strip()]

    async def set_budget_account_ids(self, db: AsyncSession, external_ids: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in external_ids if str(item).strip()]
        payload = json.dumps(cleaned)
        row = await self._get_row(db, _BUDGET_ACCOUNTS_KEY)
        if row is None:
            db.add(AppSettingRow(key=_BUDGET_ACCOUNTS_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()
        return cleaned

    async def get_status(self, db: AsyncSession) -> QuickFileConfigStatus:
        config = await self.get_config(db)
        sync_row = await self._get_row(db, _LAST_SYNC_KEY)
        last_sync = sync_row.value if sync_row else None
        configured = bool(
            config.account_number and config.api_key and config.application_id
        )
        return QuickFileConfigStatus(
            account_number=config.account_number,
            api_key_set=bool(config.api_key),
            application_id=config.application_id,
            configured=configured,
            last_sync_at=last_sync,
            budget_account_external_ids=await self.get_budget_account_ids(db),
        )

    async def set_config(
        self, db: AsyncSession, config: QuickFileConfig
    ) -> QuickFileConfigStatus:
        current = await self.get_config(db)
        if not config.api_key:
            config.api_key = current.api_key
        row = await self._get_row(db, _QUICKFILE_KEY)
        payload = seal_json(config.model_dump())
        if row is None:
            db.add(AppSettingRow(key=_QUICKFILE_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()
        return await self.get_status(db)

    async def mark_synced(self, db: AsyncSession) -> None:
        await self._set_timestamp(db, _LAST_SYNC_KEY)

    async def needs_full_history_import(self, db: AsyncSession) -> bool:
        """True until a successful long-lookback bank-line import has completed."""
        row = await self._get_row(db, _FULL_IMPORT_KEY)
        return row is None or not (row.value or "").strip()

    async def mark_full_history_imported(self, db: AsyncSession) -> None:
        await self._set_timestamp(db, _FULL_IMPORT_KEY)

    async def _set_timestamp(self, db: AsyncSession, key: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row = await self._get_row(db, key)
        if row is None:
            db.add(AppSettingRow(key=key, value=now))
        else:
            row.value = now
        await db.commit()


quickfile_settings_service = QuickFileSettingsService()
