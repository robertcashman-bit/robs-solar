"""Lunch Flow credential storage."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.finance import LunchFlowConfig, LunchFlowConfigStatus
from app.services.finance.finance_calc import MonthlyFlow
from app.services.settings_crypto import open_json, seal_json

_CONFIG_KEY = "lunchflow"
_LEGACY_CONFIG_KEY = "lunch_flow"
_LAST_SYNC_KEY = "lunchflow_last_sync_at"
_LEGACY_LAST_SYNC_KEY = "lunch_flow_last_sync_at"
_LAST_TEST_KEY = "lunchflow_last_test_at"
_LEGACY_LAST_TEST_KEY = "lunch_flow_last_test_at"
_MONTHLY_FLOW_KEY = "lunchflow_monthly_flow"
_FULL_IMPORT_KEY = "lunchflow_full_import_at"


class LunchFlowSettingsService:
    def _env_config(self) -> LunchFlowConfig:
        key = (
            settings.lunchflow_api_key
            or os.environ.get("LUNCHFLOW_API_KEY", "")
            or os.environ.get("LUNCH_FLOW_API_KEY", "")
        )
        return LunchFlowConfig(api_key=key.strip())

    def env_configured(self) -> bool:
        return bool(self._env_config().api_key)

    async def _get_row(self, db: AsyncSession, key: str) -> AppSettingRow | None:
        return await db.scalar(select(AppSettingRow).where(AppSettingRow.key == key))

    async def _get_first_row(self, db: AsyncSession, *keys: str) -> AppSettingRow | None:
        for key in keys:
            row = await self._get_row(db, key)
            if row is not None:
                return row
        return None

    async def get_config(self, db: AsyncSession) -> LunchFlowConfig:
        row = await self._get_first_row(db, _CONFIG_KEY, _LEGACY_CONFIG_KEY)
        env = self._env_config()
        if row is None or not (row.value or "").strip():
            return env
        stored = LunchFlowConfig.model_validate(open_json(row.value))
        return LunchFlowConfig(api_key=stored.api_key or env.api_key)

    async def get_status(self, db: AsyncSession) -> LunchFlowConfigStatus:
        config = await self.get_config(db)
        sync_row = await self._get_first_row(db, _LAST_SYNC_KEY, _LEGACY_LAST_SYNC_KEY)
        test_row = await self._get_first_row(db, _LAST_TEST_KEY, _LEGACY_LAST_TEST_KEY)
        configured = bool(config.api_key)
        connected = bool((sync_row and sync_row.value) or (test_row and test_row.value))
        return LunchFlowConfigStatus(
            api_key_set=configured,
            configured=configured,
            connected=connected,
            last_sync_at=sync_row.value if sync_row else None,
        )

    async def set_config(
        self, db: AsyncSession, config: LunchFlowConfig
    ) -> LunchFlowConfigStatus:
        current = await self.get_config(db)
        if not config.api_key:
            config.api_key = current.api_key
        row = await self._get_first_row(db, _CONFIG_KEY, _LEGACY_CONFIG_KEY)
        payload = seal_json(config.model_dump())
        if row is None:
            db.add(AppSettingRow(key=_CONFIG_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()
        return await self.get_status(db)

    async def mark_synced(self, db: AsyncSession) -> None:
        await self._set_timestamp(db, _LAST_SYNC_KEY)

    async def mark_tested(self, db: AsyncSession) -> None:
        await self._set_timestamp(db, _LAST_TEST_KEY)

    async def needs_full_history_import(self, db: AsyncSession) -> bool:
        """True until a successful long-lookback transaction import has completed."""
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

    async def get_monthly_flow(self, db: AsyncSession) -> MonthlyFlow:
        """Last 30-day Open Banking income/spend stored at sync time. Never overwrites snapshots."""
        row = await self._get_row(db, _MONTHLY_FLOW_KEY)
        if row is None:
            return MonthlyFlow()
        try:
            payload = json.loads(row.value)
        except json.JSONDecodeError:
            return MonthlyFlow()
        return MonthlyFlow(
            income_gbp=round(float(payload.get("income_gbp") or 0), 2),
            spending_gbp=round(float(payload.get("spending_gbp") or 0), 2),
            as_of=str(payload.get("as_of") or ""),
        )

    async def set_monthly_flow(
        self, db: AsyncSession, income_gbp: float, spending_gbp: float
    ) -> None:
        payload = json.dumps(
            {
                "income_gbp": round(income_gbp, 2),
                "spending_gbp": round(spending_gbp, 2),
                "as_of": datetime.now(timezone.utc).isoformat(),
            }
        )
        row = await self._get_row(db, _MONTHLY_FLOW_KEY)
        if row is None:
            db.add(AppSettingRow(key=_MONTHLY_FLOW_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()


lunchflow_settings_service = LunchFlowSettingsService()
