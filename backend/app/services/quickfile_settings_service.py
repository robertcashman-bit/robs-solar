"""QuickFile credential settings — env seed with optional DB override."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow, FinanceTransactionRow
from app.schemas.finance import QuickFileConfig, QuickFileConfigStatus
from app.services.finance.sync_lookback import (
    QUICKFILE_SATISFIED_LOOKBACK_DAYS,
    QUICKFILE_SUBSTANTIAL_SPAN_DAYS,
    QUICKFILE_SUBSTANTIAL_TX_MIN,
)
from app.services.settings_crypto import open_json, seal_json

logger = logging.getLogger(__name__)

_QUICKFILE_KEY = "quickfile"
_LAST_SYNC_KEY = "quickfile_last_sync_at"
_FULL_IMPORT_KEY = "quickfile_full_import_at"
# Days covered by the last successful history import. Automatic syncs are satisfied
# once this is >= QUICKFILE_SATISFIED_LOOKBACK_DAYS (~1 year). Extending to the
# ~10-year QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS window requires force_full=True.
_FULL_IMPORT_LOOKBACK_KEY = "quickfile_full_import_lookback_days"
_BUDGET_ACCOUNTS_KEY = "quickfile_budget_account_ids"
_LAST_ERROR_KEY = "quickfile_last_error"
_QUOTA_EXHAUSTED_KEY = "quickfile_quota_exhausted_at"

QUOTA_ERROR_SNIPPET = "API request limit exceeded"


def _config_complete(config: QuickFileConfig) -> bool:
    return bool(config.account_number and config.api_key and config.application_id)


def is_quickfile_quota_error(exc: BaseException | str) -> bool:
    text = str(exc)
    return QUOTA_ERROR_SNIPPET.lower() in text.lower()


def quota_blocked_until_tomorrow_utc(exhausted_at: str | None) -> bool:
    """True when quota was exhausted earlier today (UTC) — wait for midnight UTC."""
    if not exhausted_at:
        return False
    try:
        parsed = datetime.fromisoformat(exhausted_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date() >= datetime.now(timezone.utc).date()


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

    async def existing_quickfile_history(
        self, db: AsyncSession
    ) -> tuple[int, int]:
        """Return ``(tx_count, span_days)`` for non-deleted QuickFile transactions."""
        try:
            count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(FinanceTransactionRow)
                    .where(
                        FinanceTransactionRow.source == "quickfile",
                        FinanceTransactionRow.is_deleted.is_(False),
                    )
                )
                or 0
            )
        except Exception:
            logger.warning("Could not count QuickFile transactions", exc_info=True)
            return 0, 0
        if count <= 0:
            return 0, 0
        try:
            min_posted = await db.scalar(
                select(func.min(FinanceTransactionRow.posted_on)).where(
                    FinanceTransactionRow.source == "quickfile",
                    FinanceTransactionRow.is_deleted.is_(False),
                )
            )
            max_posted = await db.scalar(
                select(func.max(FinanceTransactionRow.posted_on)).where(
                    FinanceTransactionRow.source == "quickfile",
                    FinanceTransactionRow.is_deleted.is_(False),
                )
            )
        except Exception:
            logger.warning("Could not read QuickFile transaction span", exc_info=True)
            return count, 0
        if not min_posted or not max_posted:
            return count, 0
        try:
            start = date.fromisoformat(str(min_posted)[:10])
            end = date.fromisoformat(str(max_posted)[:10])
        except ValueError:
            return count, 0
        span = max(0, (end - start).days)
        return count, span

    def history_is_substantial(self, count: int, span_days: int) -> bool:
        return (
            count >= QUICKFILE_SUBSTANTIAL_TX_MIN
            and span_days >= QUICKFILE_SUBSTANTIAL_SPAN_DAYS
        )

    async def get_status(self, db: AsyncSession) -> QuickFileConfigStatus:
        config = await self.get_config(db)
        sync_row = await self._get_row(db, _LAST_SYNC_KEY)
        last_sync = sync_row.value if sync_row else None
        error_row = await self._get_row(db, _LAST_ERROR_KEY)
        quota_row = await self._get_row(db, _QUOTA_EXHAUSTED_KEY)
        configured = _config_complete(config)
        return QuickFileConfigStatus(
            account_number=config.account_number,
            api_key_set=bool(config.api_key),
            application_id=config.application_id,
            configured=configured,
            connected=configured,
            last_sync_at=last_sync,
            budget_account_external_ids=await self.get_budget_account_ids(db),
            last_error=error_row.value if error_row and error_row.value else None,
            quota_exhausted_at=quota_row.value if quota_row and quota_row.value else None,
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
        await self.clear_last_error(db)

    async def record_error(self, db: AsyncSession, message: str) -> None:
        text = (message or "").strip() or "QuickFile error"
        await self._set_value(db, _LAST_ERROR_KEY, text[:500])
        if is_quickfile_quota_error(text):
            await self._set_timestamp(db, _QUOTA_EXHAUSTED_KEY)

    async def clear_last_error(self, db: AsyncSession) -> None:
        for key in (_LAST_ERROR_KEY, _QUOTA_EXHAUSTED_KEY):
            row = await self._get_row(db, key)
            if row is not None:
                await db.delete(row)
        await db.commit()

    async def is_quota_blocked(self, db: AsyncSession) -> bool:
        row = await self._get_row(db, _QUOTA_EXHAUSTED_KEY)
        return quota_blocked_until_tomorrow_utc(row.value if row else None)

    async def needs_full_history_import(self, db: AsyncSession) -> bool:
        """True only when there is no year-class history yet.

        Missing markers no longer mean “run 3650 days now”. If Neon already holds
        substantial QuickFile transactions, seed satisfied markers (~365 days) and
        return False. Extending to the 10-year window requires ``force_full=True``.
        """
        lookback_days = await self._stored_lookback_days(db)
        if lookback_days is not None and lookback_days >= QUICKFILE_SATISFIED_LOOKBACK_DAYS:
            return False

        count, span_days = await self.existing_quickfile_history(db)
        if self.history_is_substantial(count, span_days):
            seeded = max(span_days, QUICKFILE_SATISFIED_LOOKBACK_DAYS)
            await self.mark_full_history_imported(db, lookback_days=seeded)
            return False

        # No markers and no substantial history — initial year import still needed.
        return True

    async def _stored_lookback_days(self, db: AsyncSession) -> int | None:
        row = await self._get_row(db, _FULL_IMPORT_KEY)
        if row is None or not (row.value or "").strip():
            return None
        lookback_row = await self._get_row(db, _FULL_IMPORT_LOOKBACK_KEY)
        if lookback_row is None or not (lookback_row.value or "").strip():
            return None
        try:
            return int(str(lookback_row.value).strip())
        except ValueError:
            return None

    async def mark_full_history_imported(
        self, db: AsyncSession, *, lookback_days: int | None = None
    ) -> None:
        # Default = satisfied year window. force_full callers pass 3650 explicitly.
        days = (
            QUICKFILE_SATISFIED_LOOKBACK_DAYS
            if lookback_days is None
            else int(lookback_days)
        )
        await self._set_timestamp(db, _FULL_IMPORT_KEY)
        await self._set_value(db, _FULL_IMPORT_LOOKBACK_KEY, str(days))

    async def clear_full_history_import(self, db: AsyncSession) -> None:
        """One-shot: drop full-import markers so the next sync can use deep lookback.

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
