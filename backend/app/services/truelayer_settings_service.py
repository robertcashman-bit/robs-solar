"""TrueLayer credential and token storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.finance import TrueLayerConfig, TrueLayerConfigStatus
from app.services.finance.finance_calc import MonthlyFlow

_CONFIG_KEY = "truelayer"
_TOKENS_KEY = "truelayer_tokens"
_LAST_SYNC_KEY = "truelayer_last_sync_at"
_MONTHLY_FLOW_KEY = "truelayer_monthly_flow"


class TrueLayerSettingsService:
    def _env_config(self) -> TrueLayerConfig:
        return TrueLayerConfig(
            client_id=settings.truelayer_client_id,
            client_secret=settings.truelayer_client_secret,
            redirect_uri=settings.truelayer_redirect_uri,
            environment=settings.truelayer_environment,
        )

    def env_configured(self) -> bool:
        env = self._env_config()
        return bool(env.client_id and env.client_secret and env.redirect_uri)

    async def _get_row(self, db: AsyncSession, key: str) -> AppSettingRow | None:
        return await db.scalar(select(AppSettingRow).where(AppSettingRow.key == key))

    async def get_config(self, db: AsyncSession) -> TrueLayerConfig:
        row = await self._get_row(db, _CONFIG_KEY)
        if row is None:
            return self._env_config()
        stored = TrueLayerConfig.model_validate(json.loads(row.value))
        env = self._env_config()
        return TrueLayerConfig(
            client_id=stored.client_id or env.client_id,
            client_secret=stored.client_secret or env.client_secret,
            redirect_uri=stored.redirect_uri or env.redirect_uri,
            environment=stored.environment or env.environment,
        )

    async def get_tokens(self, db: AsyncSession) -> dict[str, str]:
        row = await self._get_row(db, _TOKENS_KEY)
        if row is None:
            return {}
        return json.loads(row.value)

    async def set_tokens(self, db: AsyncSession, tokens: dict[str, str]) -> None:
        row = await self._get_row(db, _TOKENS_KEY)
        payload = json.dumps(tokens)
        if row is None:
            db.add(AppSettingRow(key=_TOKENS_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()

    async def get_status(self, db: AsyncSession) -> TrueLayerConfigStatus:
        config = await self.get_config(db)
        tokens = await self.get_tokens(db)
        sync_row = await self._get_row(db, _LAST_SYNC_KEY)
        configured = bool(config.client_id and config.client_secret and config.redirect_uri)
        connected = bool(tokens.get("refresh_token") or tokens.get("access_token"))
        return TrueLayerConfigStatus(
            client_id=config.client_id,
            client_secret_set=bool(config.client_secret),
            redirect_uri=config.redirect_uri,
            environment=config.environment,
            configured=configured,
            connected=connected,
            last_sync_at=sync_row.value if sync_row else None,
        )

    async def set_config(self, db: AsyncSession, config: TrueLayerConfig) -> TrueLayerConfigStatus:
        current = await self.get_config(db)
        if not config.client_secret:
            config.client_secret = current.client_secret
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

    async def get_monthly_flow(self, db: AsyncSession) -> MonthlyFlow:
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


truelayer_settings_service = TrueLayerSettingsService()
