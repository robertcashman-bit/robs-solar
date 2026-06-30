from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.schemas.domain import AuditListResponse
from app.services.audit_service import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditListResponse)
async def list_audit(
    _: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditListResponse:
    return await audit_service.list_entries(db, limit=limit, offset=offset)
