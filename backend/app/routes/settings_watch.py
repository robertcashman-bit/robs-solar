from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_viewer
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.services.settings_watch_service import settings_watch_service

router = APIRouter(prefix="/controls/settings-watch", tags=["controls"])


@router.get("/status")
async def settings_watch_status(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await settings_watch_service.status(db)


@router.get("/changes")
async def settings_watch_changes(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    changes = await settings_watch_service.list_changes(db, limit=limit)
    return {"changes": changes, "count": len(changes)}


@router.post("/poll")
async def settings_watch_poll_now(
    _: SessionData = Depends(require_viewer),
) -> dict:
    """Force one read-only settings poll (never writes to the inverter)."""
    event = await settings_watch_service.poll_once()
    if event is None:
        return {
            "changed": False,
            "message": "No change (or watcher disabled / settings unavailable)",
        }
    return {
        "changed": True,
        "id": event.id,
        "timestamp": event.timestamp.isoformat(),
        "note": event.note,
        "fingerprint": event.fingerprint,
    }
