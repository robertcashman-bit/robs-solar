"""QuickFile credential settings — env seed with optional DB override."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.finance import QuickFileConfig, QuickFileConfigStatus
from app.services.finance.sync_lookback import QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS
from app.services.settings_crypto import open_json, seal_json

logger = logging.getLogger(__name__)

_QUICKFILE_KEY = "quickfile"
_LAST_SYNC_KEY = "quickfile_last_sync_at"
_FULL_IMPORT_KEY = "quickfile_full_import_at"
# Days covered by the last successful long-lookback import. Missing or smaller than
# QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS marks the prior full import as stale so the next
# sync re-runs deep history (fingerprints keep existing txs idempotent).
_FULL_IMPORT_LOOKBACK_KEY = "quickfile_full_import_lookback_days"
_BUDGET_ACCOUNTS_KEY = "quickfile_budget_account_ids"


def _config_complete(config: QuickFileConfig) -> bool:
    return bool(config.account_number and config.api_key and config.application_id)


class QuickFileSettingsService:
    def _env_config(self) -> QuickFileConfig:
        return QuickFileConfig(
            account_number=settings.quickfile_account_number,
            api_key=settings.quickfile_api_key,
            application_id=settings.quickfile_application_id,
        )

    def env_configured(self) -> bool:
        return _config_complete(self._env_config())

    async def _get_row(self, db: AsyncSession, key: str) -> AppSettingRow | None:
        return await db.scalar(select(AppSettingRow).where(AppSettingRow.key == key))

    def _read_stored(self, raw: str | None) -> QuickFileConfig | None:
        """Decrypt a Neon row. Returns None when missing, empty, or unreadable."""
        if not (raw or "").strip():
            return None
        try:
            data = open_json(raw or "")
            stored = QuickFileConfig.model_validate(data)
        except Exception:
            logger.warning(
                "QuickFile app_settings row unreadable — falling back to env",
                exc_info=True,
            )
            return None
        if not any([stored.account_number, stored.api_key, stored.application_id]):
            return None
        return stored

    async def _persist_config(self, db: AsyncSession, config: QuickFileConfig) -> None:
        """Seal a complete config into Neon. Never write incomplete payloads."""
        if not _config_complete(config):
            return
        try:
            payload = seal_json(config.model_dump())
            row = await self._get_row(db, _QUICKFILE_KEY)
            if row is None:
                db.add(AppSettingRow(key=_QUICKFILE_KEY, value=payload))
            else:
                row.value = payload
            await db.commit()
        except Exception:
            logger.warning(
                "Could not persist QuickFile config to app_settings",
                exc_info=True,
            )

    async def get_config(self, db: AsyncSession) -> QuickFileConfig:
        """Return merged QuickFile credentials (Neon preferred, env fills gaps).

        Never raises because of a corrupt sealed blob — falls back to env.
        When the resolved config is complete and Neon is missing/unreadable/
        incomplete, persists a sealed copy so later requests survive brief env gaps.
        """
        env = self._env_config()
        row = await self._get_row(db, _QUICKFILE_KEY)
        stored = self._read_stored(row.value if row is not None else None)

        if stored is None:
            merged = env
            if _config_complete(merged):
                await self._persist_config(db, merged)
            return merged

        merged = QuickFileConfig(
            account_number=stored.account_number or env.account_number,
            api_key=stored.api_key or env.api_key,
            application_id=stored.application_id or env.application_id,
        )
        if _config_complete(merged) and not _config_complete(stored):
            await self._persist_config(db, merged)
        return merged

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
        configured = _config_complete(config)
        return QuickFileConfigStatus(
            account_number=config.account_number,
            api_key_set=bool(config.api_key),
            application_id=config.application_id,
            configured=configured,
            connected=configured,
            last_sync_at=last_sync,
            budget_account_external_ids=await self.get_budget_account_ids(db),
        )

    async def set_config(
        self, db: AsyncSession, config: QuickFileConfig
    ) -> QuickFileConfigStatus:
        """Save credentials without wiping a complete config with blanks."""
        current = await self.get_config(db)
        merged = QuickFileConfig(
            account_number=(config.account_number or "").strip() or current.account_number,
            api_key=(config.api_key or "").strip() or current.api_key,
            application_id=(config.application_id or "").strip() or current.application_id,
        )
        if not _config_complete(merged):
            # Do not overwrite a complete stored row with an incomplete payload.
            return await self.get_status(db)
        await self._persist_config(db, merged)
        return await self.get_status(db)

    async def mark_synced(self, db: AsyncSession) -> None:
        await self._set_timestamp(db, _LAST_SYNC_KEY)

    async def needs_full_history_import(self, db: AsyncSession) -> bool:
        """True until a successful long-lookback bank-line import has completed.

        Also true when a prior full import used a shorter lookback than
        ``QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS`` (stale flag). Clearing via
        ``clear_full_history_import`` is the documented one-shot to force another
        deep pass; existing transaction fingerprints stay idempotent.
        """
        row = await self._get_row(db, _FULL_IMPORT_KEY)
        if row is None or not (row.value or "").strip():
            return True
        lookback_row = await self._get_row(db, _FULL_IMPORT_LOOKBACK_KEY)
        if lookback_row is None or not (lookback_row.value or "").strip():
            return True
        try:
            stored_days = int(str(lookback_row.value).strip())
        except ValueError:
            return True
        return stored_days < QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS

    async def mark_full_history_imported(self, db: AsyncSession) -> None:
        await self._set_timestamp(db, _FULL_IMPORT_KEY)
        await self._set_value(
            db, _FULL_IMPORT_LOOKBACK_KEY, str(QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS)
        )

    async def clear_full_history_import(self, db: AsyncSession) -> None:
        """One-shot: drop full-import markers so the next sync uses deep lookback.

        Does not delete finance transactions. Call via ``sync(..., force_full=True)``
        or by clearing ``quickfile_full_import_at`` /
        ``quickfile_full_import_lookback_days`` in app_settings.
        """
        for key in (_FULL_IMPORT_KEY, _FULL_IMPORT_LOOKBACK_KEY):
            row = await self._get_row(db, key)
            if row is not None:
                await db.delete(row)
        await db.commit()

    async def _set_timestamp(self, db: AsyncSession, key: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._set_value(db, key, now)

    async def _set_value(self, db: AsyncSession, key: str, value: str) -> None:
        row = await self._get_row(db, key)
        if row is None:
            db.add(AppSettingRow(key=key, value=value))
        else:
            row.value = value
        await db.commit()


quickfile_settings_service = QuickFileSettingsService()
