from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, validate_csrf
from app.auth.sessions import SessionData
from app.config import settings
from app.db.session import get_db
from app.schemas.domain import (
    AiAssessment,
    AiChatRequest,
    AiChatResponse,
    AiStatusResponse,
)
from app.services.ai_advisor_service import ai_advisor_service

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status", response_model=AiStatusResponse)
async def ai_status(_: SessionData = Depends(require_admin)) -> AiStatusResponse:
    return AiStatusResponse(
        enabled=ai_advisor_service.enabled,
        model=settings.ai_model if ai_advisor_service.enabled else "",
        reason=ai_advisor_service.status_reason(),
    )


def _require_enabled() -> None:
    if not ai_advisor_service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ai_advisor_service.status_reason() or "AI assistant unavailable",
        )


@router.post("/assess", response_model=AiAssessment)
async def assess(
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AiAssessment:
    _ = session
    _require_enabled()
    try:
        return await ai_advisor_service.assess(db)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI assessment failed: {exc}",
        ) from exc


@router.post("/chat", response_model=AiChatResponse)
async def chat(
    body: AiChatRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AiChatResponse:
    validate_csrf(request, session)
    _require_enabled()
    try:
        return await ai_advisor_service.chat(db, body.messages)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI chat failed: {exc}",
        ) from exc
