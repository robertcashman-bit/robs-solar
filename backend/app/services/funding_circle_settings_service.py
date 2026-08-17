"""Funding Circle loan settings stored in app_settings."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSettingRow
from app.schemas.finance import FundingCircleConfig, FundingCircleConfigStatus

_CONFIG_KEY = "funding_circle"
_LAST_SYNC_KEY = "funding_circle_last_sync_at"


class FundingCircleSettingsService:
    async def _get_row(self, db: AsyncSession, key: str) -> AppSettingRow | None:
        return await db.scalar(select(AppSettingRow).where(AppSettingRow.key == key))

    async def get_config(self, db: AsyncSession) -> FundingCircleConfig:
        row = await self._get_row(db, _CONFIG_KEY)
        if row is None:
            return FundingCircleConfig()
        return FundingCircleConfig.model_validate(json.loads(row.value))

    async def get_status(self, db: AsyncSession) -> FundingCircleConfigStatus:
        config = await self.get_config(db)
        sync_row = await self._get_row(db, _LAST_SYNC_KEY)
        last_sync = sync_row.value if sync_row else None
        configured = config.outstanding_gbp is not None or bool(config.last_source)
        return FundingCircleConfigStatus(
            configured=configured,
            auto_sync=config.auto_sync,
            outstanding_gbp=config.outstanding_gbp,
            original_gbp=config.original_gbp,
            apr_pct=config.apr_pct,
            minimum_payment_gbp=config.minimum_payment_gbp,
            payment_day=config.payment_day,
            last_sync_at=last_sync,
            last_source=config.last_source,
            last_txn_on=config.last_txn_on,
            message=config.message,
        )

    async def set_config(
        self, db: AsyncSession, config: FundingCircleConfig
    ) -> FundingCircleConfigStatus:
        current = await self.get_config(db)
        merged = current.model_copy(update=config.model_dump(exclude_unset=True))
        row = await self._get_row(db, _CONFIG_KEY)
        payload = json.dumps(merged.model_dump())
        if row is None:
            db.add(AppSettingRow(key=_CONFIG_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()
        return await self.get_status(db)

    async def mark_synced(
        self,
        db: AsyncSession,
        *,
        source: str,
        outstanding_gbp: float | None = None,
        last_txn_on: str | None = None,
        message: str = "",
    ) -> None:
        config = await self.get_config(db)
        if outstanding_gbp is not None:
            config.outstanding_gbp = outstanding_gbp
        config.last_source = source
        config.message = message
        if last_txn_on:
            config.last_txn_on = last_txn_on
        row = await self._get_row(db, _CONFIG_KEY)
        payload = json.dumps(config.model_dump())
        if row is None:
            db.add(AppSettingRow(key=_CONFIG_KEY, value=payload))
        else:
            row.value = payload
        now = datetime.now(timezone.utc).isoformat()
        sync_row = await self._get_row(db, _LAST_SYNC_KEY)
        if sync_row is None:
            db.add(AppSettingRow(key=_LAST_SYNC_KEY, value=now))
        else:
            sync_row.value = now
        await db.commit()


funding_circle_settings_service = FundingCircleSettingsService()
