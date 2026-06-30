"""Tariff settings — stored in app_settings KV, seeded from env."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.schemas.domain import TariffSettings

_TARIFF_KEY = "tariff"


class TariffService:
    def _defaults(self) -> TariffSettings:
        return TariffSettings(
            import_rate=settings.tariff_import_rate,
            export_rate=settings.tariff_export_rate,
            currency=settings.tariff_currency,
        )

    async def get_tariff(self, db: AsyncSession) -> TariffSettings:
        result = await db.execute(
            select(AppSettingRow).where(AppSettingRow.key == _TARIFF_KEY)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return self._defaults()
        data = json.loads(row.value)
        return TariffSettings.model_validate(data)

    async def set_tariff(self, db: AsyncSession, tariff: TariffSettings) -> TariffSettings:
        result = await db.execute(
            select(AppSettingRow).where(AppSettingRow.key == _TARIFF_KEY)
        )
        row = result.scalar_one_or_none()
        payload = json.dumps(tariff.model_dump())
        if row is None:
            db.add(AppSettingRow(key=_TARIFF_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()
        return tariff


tariff_service = TariffService()
