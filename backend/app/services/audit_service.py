from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLogRow
from app.schemas.domain import AuditEntry, AuditListResponse, AuditOutcome, UserRole


class AuditService:
    async def record(
        self,
        db: AsyncSession,
        *,
        username: str,
        role: UserRole,
        action: str,
        request_payload: dict,
        validation_result: str,
        adapter_response: str | None,
        outcome: AuditOutcome,
    ) -> AuditLogRow:
        row = AuditLogRow(
            timestamp=datetime.now(timezone.utc),
            username=username,
            role=role.value,
            action=action,
            request_payload=json.dumps(request_payload),
            validation_result=validation_result,
            adapter_response=adapter_response,
            outcome=outcome.value,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    def to_entry(self, row: AuditLogRow) -> AuditEntry:
        return AuditEntry(
            id=row.id,
            timestamp=row.timestamp,
            username=row.username,
            role=UserRole(row.role),
            action=row.action,
            request_payload=json.loads(row.request_payload),
            validation_result=row.validation_result,
            adapter_response=row.adapter_response,
            outcome=AuditOutcome(row.outcome),
        )

    async def list_entries(
        self,
        db: AsyncSession,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> AuditListResponse:
        total = await db.scalar(select(func.count()).select_from(AuditLogRow))
        result = await db.execute(
            select(AuditLogRow).order_by(desc(AuditLogRow.id)).limit(limit).offset(offset)
        )
        rows = result.scalars().all()
        return AuditListResponse(
            entries=[self.to_entry(row) for row in rows],
            total=int(total or 0),
        )


audit_service = AuditService()
