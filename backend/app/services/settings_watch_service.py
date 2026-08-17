"""Read-only inverter settings watcher.

Polls adapter.get_inverter_settings(), fingerprints the meaningful fields, and
records a change event when values differ. Never writes to the inverter.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_adapter
from app.config import settings
from app.db.models import AppSettingRow, SettingsWatchChangeRow
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_LAST_FINGERPRINT_KEY = "settings_watch_last_fingerprint"
_LAST_SNAPSHOT_KEY = "settings_watch_last_snapshot"
_WATCH_FIELDS = (
    "sys_work_mode",
    "sys_work_mode_label",
    "energy_mode",
    "solar_sell",
    "export_limit_mode",
    "discharge_current_a",
    "bands",
    "active_band_slot",
)


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def normalize_settings_snapshot(payload: Any) -> dict[str, Any]:
    raw = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    snapshot: dict[str, Any] = {}
    for key in _WATCH_FIELDS:
        value = raw.get(key)
        if key == "bands" and value is not None:
            bands = []
            for band in value:
                item = band.model_dump() if hasattr(band, "model_dump") else dict(band)
                bands.append(
                    {
                        "slot": item.get("slot"),
                        "start": item.get("start"),
                        "end": item.get("end"),
                        "target_soc_pct": item.get("target_soc_pct"),
                        "grid_charge_enabled": item.get("grid_charge_enabled"),
                        "power_w": item.get("power_w"),
                    }
                )
            snapshot[key] = bands
        else:
            snapshot[key] = value
    # Keep plant identity for context (not part of fingerprint alone)
    snapshot["plant_id"] = raw.get("plant_id")
    snapshot["plant_name"] = raw.get("plant_name")
    return snapshot


def fingerprint_snapshot(snapshot: dict[str, Any]) -> str:
    material = {key: snapshot.get(key) for key in _WATCH_FIELDS}
    encoded = json.dumps(material, sort_keys=True, default=_json_default, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def diff_snapshots(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for key in _WATCH_FIELDS:
        before = previous.get(key)
        after = current.get(key)
        if before != after:
            changes.append({"field": key, "from": before, "to": after})
    return changes


class SettingsWatchService:
    async def _get_app_setting(self, db: AsyncSession, key: str) -> str | None:
        row = await db.get(AppSettingRow, key)
        return row.value if row else None

    async def _set_app_setting(self, db: AsyncSession, key: str, value: str) -> None:
        row = await db.get(AppSettingRow, key)
        if row is None:
            db.add(AppSettingRow(key=key, value=value))
        else:
            row.value = value

    async def observe_payload(
        self,
        db: AsyncSession,
        payload: Any,
        *,
        source: str = "poll",
        note: str = "",
    ) -> SettingsWatchChangeRow | None:
        snapshot = normalize_settings_snapshot(payload)
        fingerprint = fingerprint_snapshot(snapshot)
        previous_fp = await self._get_app_setting(db, _LAST_FINGERPRINT_KEY)
        previous_raw = await self._get_app_setting(db, _LAST_SNAPSHOT_KEY)
        previous_snapshot = json.loads(previous_raw) if previous_raw else None

        if previous_fp == fingerprint:
            return None

        changes = (
            diff_snapshots(previous_snapshot, snapshot)
            if previous_snapshot is not None
            else [{"field": "_baseline", "from": None, "to": "initial_snapshot"}]
        )
        event_note = note or (
            "Initial settings baseline (read-only)"
            if previous_fp is None
            else "Settings change detected (read-only poll)"
        )
        row = SettingsWatchChangeRow(
            timestamp=datetime.now(timezone.utc),
            fingerprint=fingerprint,
            previous_fingerprint=previous_fp,
            changes_json=json.dumps(changes, default=_json_default),
            snapshot_json=json.dumps(snapshot, default=_json_default),
            source=source,
            note=event_note,
        )
        db.add(row)
        await self._set_app_setting(db, _LAST_FINGERPRINT_KEY, fingerprint)
        await self._set_app_setting(
            db, _LAST_SNAPSHOT_KEY, json.dumps(snapshot, default=_json_default)
        )
        await db.commit()
        await db.refresh(row)
        if previous_fp is None:
            logger.info("Settings watch baseline stored fingerprint=%s", fingerprint[:12])
        else:
            logger.warning(
                "Settings change detected fingerprint=%s fields=%s",
                fingerprint[:12],
                [c.get("field") for c in changes],
            )
        return row

    async def poll_once(self) -> SettingsWatchChangeRow | None:
        if not settings.settings_watch_enabled:
            return None
        adapter = get_adapter()
        getter = getattr(adapter, "get_inverter_settings", None)
        if getter is None:
            return None
        payload = await getter()
        if payload is None:
            return None
        async with SessionLocal() as db:
            return await self.observe_payload(db, payload, source="poll")

    async def list_changes(self, db: AsyncSession, *, limit: int = 50) -> list[dict[str, Any]]:
        result = await db.execute(
            select(SettingsWatchChangeRow)
            .order_by(desc(SettingsWatchChangeRow.timestamp))
            .limit(limit)
        )
        rows = list(result.scalars().all())
        items: list[dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "id": row.id,
                    "timestamp": row.timestamp.isoformat(),
                    "fingerprint": row.fingerprint,
                    "previous_fingerprint": row.previous_fingerprint,
                    "changes": json.loads(row.changes_json),
                    "snapshot": json.loads(row.snapshot_json),
                    "source": row.source,
                    "note": row.note,
                }
            )
        return items

    async def status(self, db: AsyncSession) -> dict[str, Any]:
        last_fp = await self._get_app_setting(db, _LAST_FINGERPRINT_KEY)
        count = len(
            (
                await db.execute(select(SettingsWatchChangeRow.id).limit(1000))
            ).scalars().all()
        )
        latest = (
            await db.execute(
                select(SettingsWatchChangeRow)
                .order_by(desc(SettingsWatchChangeRow.timestamp))
                .limit(1)
            )
        ).scalar_one_or_none()
        return {
            "enabled": settings.settings_watch_enabled,
            "every_n_samples": settings.settings_watch_every_n_samples,
            "has_baseline": bool(last_fp),
            "last_fingerprint": last_fp,
            "change_event_count": count,
            "latest_event_at": latest.timestamp.isoformat() if latest else None,
            "read_only": True,
        }

    async def prune_old(self, db: AsyncSession) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.settings_watch_retention_days)
        await db.execute(
            delete(SettingsWatchChangeRow).where(SettingsWatchChangeRow.timestamp < cutoff)
        )
        await db.commit()


settings_watch_service = SettingsWatchService()
