import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_adapter
from app.auth.dependencies import require_admin, validate_csrf
from app.auth.sessions import SessionData
from app.config import settings
from app.db.models import AppSettingRow, ConfigSnapshotRow
from app.db.session import get_db
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.domain import AuditOutcome, RestoreResult
from app.services.audit_service import audit_service
from app.services.control_service import control_service
from app.services.tariff_service import tariff_service

router = APIRouter(prefix="/config", tags=["config"])

_BACKUP_KEY = "system_backup"


class ConfigBackupPayload(BaseModel):
    tariff: dict
    adapter_mode: str
    snapshots: list[dict] = Field(default_factory=list)


@router.get("/backup")
async def export_backup(
    _: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tariff = await tariff_service.get_tariff(db)
    result = await db.execute(
        select(ConfigSnapshotRow).order_by(ConfigSnapshotRow.timestamp.desc()).limit(20)
    )
    snapshots = [
        {
            "id": row.id,
            "timestamp": row.timestamp.isoformat(),
            "username": row.username,
            "snapshot_type": row.snapshot_type,
            "payload": json.loads(row.payload),
        }
        for row in result.scalars().all()
    ]
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "adapter_mode": settings.adapter_mode,
        "tariff": tariff.model_dump(),
        "snapshots": snapshots,
    }


@router.post("/backup/restore")
async def restore_backup(
    body: ConfigBackupPayload,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    if settings.read_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System is in read-only mode",
        )
    from app.schemas.domain import TariffSettings

    await tariff_service.set_tariff(db, TariffSettings.model_validate(body.tariff))
    db.add(
        AppSettingRow(
            key=_BACKUP_KEY,
            value=json.dumps({"restored_at": datetime.now(timezone.utc).isoformat()}),
        )
    )
    await db.commit()
    await audit_service.record(
        db,
        username=session.username,
        role=session.role,
        action="restore_backup",
        request_payload={"adapter_mode": body.adapter_mode},
        validation_result="valid",
        adapter_response=f"Restored tariff and noted {len(body.snapshots)} snapshots",
        outcome=AuditOutcome.SUCCESS,
    )
    return {"success": True, "message": "Tariff settings restored from backup"}


@router.post("/restore-last-known-good", response_model=RestoreResult)
async def restore_last_known_good(
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> RestoreResult:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    if settings.read_only:
        await audit_service.record(
            db,
            username=session.username,
            role=session.role,
            action="restore_last_known_good",
            request_payload={},
            validation_result="blocked_read_only",
            adapter_response="READ_ONLY mode enabled",
            outcome=AuditOutcome.REJECTED,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System is in read-only mode",
        )
    adapter = get_adapter()
    result = await control_service.restore_last_known_good(
        db, adapter, username=session.username, role=session.role
    )
    if not result.success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.message)
    return result
