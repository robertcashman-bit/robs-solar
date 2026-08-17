"""Finance backup and restore — local snapshot plus optional Vercel Blob.

Automatic web backup is the hosted equivalent of Custody Note's off-site copy:
serialize finance tables + relevant settings, upload to Blob when a token is
set, and restore the latest snapshot if the live database is empty after a
deploy (typical when DATABASE_URL still points at /tmp).

Never invent transactions. Restore only writes rows that are missing.
Never overwrites DATABASE_URL or SECRET_KEY.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import (
    AppSettingRow,
    BusinessFinanceSnapshotRow,
    CashflowForecastRow,
    FinanceAccountRow,
    FinanceBackupSnapshotRow,
    FinanceBudgetPlanLineRow,
    FinanceBudgetPlanRow,
    FinanceChangeAuditRow,
    FinanceHealthEventRow,
    FinanceImportBatchRow,
    FinanceInsightRow,
    FinanceLiabilityRow,
    FinancePositionSnapshotRow,
    FinanceRecurringRuleRow,
    FinanceSinkingFundRow,
    FinanceTransactionRow,
    MonthlyBudgetRow,
    PersonalFinanceSnapshotRow,
)
from app.services.finance.finance_audit_service import finance_audit_service

logger = logging.getLogger(__name__)

FINANCE_SETTING_PREFIXES = (
    "finance.",
    "truelayer",
    "lunchflow",
    "quickfile",
    "capitalontap",
    "funding_circle",
    "enable_banking",
)
UNSAFE_SETTING_KEYS = {
    "lunchflow",
    "truelayer",
    "truelayer_tokens",
    "quickfile",
    "enable_banking",
    "capitalontap",
    "funding_circle",
}
UNSAFE_SETTING_MARKERS = ("api_key", "token", "secret", "password", "pem", "refresh")

TABLE_DUMPERS: list[tuple[str, Any]] = [
    ("finance_accounts", FinanceAccountRow),
    ("finance_liabilities", FinanceLiabilityRow),
    ("finance_budget_plans", FinanceBudgetPlanRow),
    ("finance_budget_plan_lines", FinanceBudgetPlanLineRow),
    ("monthly_budget", MonthlyBudgetRow),
    ("finance_transactions", FinanceTransactionRow),
    ("finance_import_batches", FinanceImportBatchRow),
    ("finance_change_audit", FinanceChangeAuditRow),
    ("finance_sinking_funds", FinanceSinkingFundRow),
    ("finance_recurring_rules", FinanceRecurringRuleRow),
    ("finance_health_events", FinanceHealthEventRow),
    ("personal_finance_snapshots", PersonalFinanceSnapshotRow),
    ("business_finance_snapshots", BusinessFinanceSnapshotRow),
    ("finance_position_snapshots", FinancePositionSnapshotRow),
    ("cashflow_forecast", CashflowForecastRow),
    ("finance_insights", FinanceInsightRow),
]


def _is_safe_setting_key(key: str) -> bool:
    if key in UNSAFE_SETTING_KEYS:
        return False
    lowered = key.lower()
    return not any(marker in lowered for marker in UNSAFE_SETTING_MARKERS)


def _backup_fernet():
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    digest = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def wrap_blob_payload(payload: dict[str, Any]) -> bytes:
    raw = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    wrapper = {
        "kind": "robs-finance-backup",
        "version": 2,
        "encrypted": True,
        "created_at": payload.get("created_at"),
        "ciphertext": _backup_fernet().encrypt(raw).decode("ascii"),
    }
    return json.dumps(wrapper, separators=(",", ":")).encode("utf-8")


def unwrap_blob_payload(data: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(data, dict) or data.get("kind") != "robs-finance-backup":
        return None
    if data.get("encrypted") and data.get("ciphertext"):
        try:
            inner = json.loads(_backup_fernet().decrypt(str(data["ciphertext"]).encode("ascii")))
        except Exception:
            logger.exception("Failed to decrypt finance backup")
            return None
        if not isinstance(inner, dict) or inner.get("kind") != "robs-finance-backup":
            return None
        return inner
    return data


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _row_to_dict(row: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, datetime):
            out[column.name] = _iso(value)
        else:
            out[column.name] = value
    return out


async def dump_finance_payload(db: AsyncSession) -> dict[str, Any]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for name, model in TABLE_DUMPERS:
        rows = (await db.execute(select(model))).scalars().all()
        tables[name] = [_row_to_dict(row) for row in rows]
    settings_rows = (await db.execute(select(AppSettingRow))).scalars().all()
    settings = {
        row.key: row.value
        for row in settings_rows
        if any(row.key.startswith(prefix) for prefix in FINANCE_SETTING_PREFIXES)
        and _is_safe_setting_key(row.key)
    }
    return {
        "kind": "robs-finance-backup",
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
        "settings": settings,
    }


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


async def _upload_blob(payload: bytes, pathname: str) -> str | None:
    token = get_settings().blob_read_write_token
    if not token:
        return None
    import httpx

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.put(
                f"https://blob.vercel-storage.com/{pathname}",
                content=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-api-version": "7",
                    "x-content-type": "application/json",
                    "x-vercel-blob-access": "private",
                    "x-add-random-suffix": "0",
                    "x-allow-overwrite": "1",
                },
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.exception("Vercel Blob finance backup upload failed")
        return None
    if isinstance(data, dict):
        return str(data.get("url") or "")
    return None


async def _list_blob_backups() -> list[dict[str, str]]:
    token = get_settings().blob_read_write_token
    if not token:
        return []
    import httpx

    prefix = get_settings().finance_backup_prefix.rstrip("/") + "/"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://blob.vercel-storage.com",
                params={"prefix": prefix, "limit": "50"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-api-version": "7",
                },
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.exception("Vercel Blob finance backup list failed")
        return []
    blobs = data.get("blobs") if isinstance(data, dict) else []
    out: list[dict[str, str]] = []
    for item in blobs or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "")
        pathname = str(item.get("pathname") or "")
        if url:
            out.append({"url": url, "pathname": pathname})
    out.sort(key=lambda item: item.get("pathname") or "", reverse=True)
    return out


async def _download_blob(url: str) -> dict[str, Any] | None:
    import httpx

    token = get_settings().blob_read_write_token
    headers = {"x-api-version": "7"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.exception("Failed to download finance backup from %s", url)
        return None
    return unwrap_blob_payload(data) if isinstance(data, dict) else None


async def create_backup(
    db: AsyncSession,
    *,
    trigger: str,
    actor: str = "system",
    persist: bool = True,
) -> dict[str, Any]:
    payload = await dump_finance_payload(db)
    raw = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = get_settings().finance_backup_prefix.rstrip("/")
    pathname = f"{prefix}/finance-{stamp}.json"
    blob_body = wrap_blob_payload(payload)
    blob_url = await _upload_blob(blob_body, pathname)
    if blob_url:
        await _upload_blob(blob_body, f"{prefix}/latest.json")
    location = "blob" if blob_url else "local"
    checksum = hashlib.sha256(raw).hexdigest()
    tables = payload.get("tables") or {}
    row = FinanceBackupSnapshotRow(
        created_at=datetime.now(timezone.utc),
        trigger=trigger[:32],
        location=location,
        web_url=blob_url or "",
        checksum=checksum,
        account_count=len(tables.get("finance_accounts") or []),
        transaction_count=len(tables.get("finance_transactions") or []),
        payload_json=raw.decode("utf-8") if location == "local" else "",
    )
    db.add(row)
    await db.flush()
    await finance_audit_service.record(
        db,
        entity_type="backup",
        entity_id=str(row.id),
        field="create",
        previous_value="",
        new_value=location,
        actor=actor,
    )
    if persist:
        await db.commit()
    return {
        "id": row.id,
        "created_at": _iso(row.created_at),
        "trigger": row.trigger,
        "location": location,
        "web_url": blob_url,
        "checksum": checksum,
        "byte_size": len(raw),
        "status": "ok",
        "web_backup_configured": bool(get_settings().blob_read_write_token),
    }


async def list_backups(db: AsyncSession) -> dict[str, Any]:
    rows = (
        (
            await db.execute(
                select(FinanceBackupSnapshotRow)
                .order_by(FinanceBackupSnapshotRow.created_at.desc())
                .limit(40)
            )
        )
        .scalars()
        .all()
    )
    local = [
        {
            "id": row.id,
            "created_at": _iso(row.created_at),
            "trigger": row.trigger,
            "location": row.location,
            "web_url": row.web_url,
            "checksum": row.checksum,
            "account_count": row.account_count,
            "transaction_count": row.transaction_count,
        }
        for row in rows
    ]
    remote = await _list_blob_backups()
    return {
        "local": local,
        "remote": remote,
        "web_backup_configured": bool(get_settings().blob_read_write_token),
    }


def _restore_model(model: Any, item: dict[str, Any]) -> Any:
    kwargs: dict[str, Any] = {}
    for column in model.__table__.columns:
        if column.name not in item:
            continue
        value = item[column.name]
        if isinstance(column.type, DateTime):
            parsed = _parse_dt(value)
            if parsed is not None:
                kwargs[column.name] = parsed
                continue
        kwargs[column.name] = value
    return model(**kwargs)


async def restore_payload(
    db: AsyncSession, payload: dict[str, Any], *, actor: str
) -> dict[str, Any]:
    if payload.get("kind") != "robs-finance-backup":
        raise ValueError("Not a Rob's Finance backup")
    tables = payload.get("tables") or {}
    restored: dict[str, int] = {}
    for name, model in TABLE_DUMPERS:
        items = tables.get(name) or []
        existing_ids = set((await db.execute(select(model.id))).scalars().all())
        added = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            row_id = item.get("id")
            if row_id in existing_ids:
                continue
            db.add(_restore_model(model, item))
            added += 1
        restored[name] = added
    settings = payload.get("settings") or {}
    setting_added = 0
    for key, value in settings.items():
        if not isinstance(key, str) or not any(
            key.startswith(prefix) for prefix in FINANCE_SETTING_PREFIXES
        ):
            continue
        existing = await db.get(AppSettingRow, key)
        if existing is None:
            db.add(AppSettingRow(key=key, value=str(value)))
            setting_added += 1
    restored["settings"] = setting_added
    await finance_audit_service.record(
        db,
        entity_type="backup",
        entity_id="restore",
        field="restore",
        previous_value="",
        new_value=json.dumps(restored),
        actor=actor,
    )
    await db.commit()
    return {"restored": restored, "source_created_at": payload.get("created_at")}


async def restore_local_snapshot(
    db: AsyncSession, snapshot_id: int, *, actor: str
) -> dict[str, Any]:
    row = await db.get(FinanceBackupSnapshotRow, snapshot_id)
    if row is None:
        raise ValueError("Backup snapshot not found")
    if row.web_url:
        payload = await _download_blob(row.web_url)
        if payload is None:
            raise ValueError("Could not download web backup")
        return await restore_payload(db, payload, actor=actor)
    if not row.payload_json:
        raise ValueError("Local snapshot has no payload")
    payload = json.loads(row.payload_json)
    return await restore_payload(db, payload, actor=actor)


async def finance_store_is_empty(db: AsyncSession) -> bool:
    accounts = int(
        (await db.execute(select(func.count()).select_from(FinanceAccountRow))).scalar_one()
    )
    txs = int(
        (await db.execute(select(func.count()).select_from(FinanceTransactionRow))).scalar_one()
    )
    debts = int(
        (await db.execute(select(func.count()).select_from(FinanceLiabilityRow))).scalar_one()
    )
    return accounts == 0 and txs == 0 and debts == 0


async def restore_latest_web_backup_if_empty(db: AsyncSession) -> dict[str, Any] | None:
    if not await finance_store_is_empty(db):
        return None
    remote = await _list_blob_backups()
    if not remote:
        return None
    latest = remote[0]
    payload = await _download_blob(latest["url"])
    if payload is None:
        return None
    result = await restore_payload(db, payload, actor="self_heal")
    result["web_url"] = latest["url"]
    logger.info("Restored finance data from web backup %s", latest["url"])
    return result
