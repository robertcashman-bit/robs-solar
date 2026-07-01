"""Optimisation mode settings — read_only (default), confirm, or auto."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSettingRow
from app.schemas.domain import OptimisationMode, OptimisationModeSettings

_KEY = "optimisation_mode"


class OptimisationModeService:
    async def get_settings(self, db: AsyncSession) -> OptimisationModeSettings:
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _KEY))
        if row is None:
            return OptimisationModeSettings()
        try:
            return OptimisationModeSettings.model_validate(json.loads(row.value))
        except (json.JSONDecodeError, ValueError):
            return OptimisationModeSettings()

    async def set_settings(
        self, db: AsyncSession, payload: OptimisationModeSettings
    ) -> OptimisationModeSettings:
        encoded = json.dumps(payload.model_dump())
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _KEY))
        if row:
            row.value = encoded
        else:
            db.add(AppSettingRow(key=_KEY, value=encoded))
        await db.commit()
        return payload

    def can_auto_apply(
        self,
        settings: OptimisationModeSettings,
        recommendation_type: str,
    ) -> bool:
        if settings.mode != OptimisationMode.AUTO:
            return False
        mapping = {
            "charge_window": settings.allow_auto_charge_window_changes,
            "discharge_window": settings.allow_auto_discharge_window_changes,
            "min_reserve": settings.allow_auto_reserve_changes,
            "grid_charge": settings.allow_auto_grid_charge_changes,
        }
        return mapping.get(recommendation_type, False)


optimisation_mode_service = OptimisationModeService()
