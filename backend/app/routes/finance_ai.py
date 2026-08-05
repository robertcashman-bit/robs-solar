from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, validate_csrf
from app.auth.sessions import SessionData
from app.config import settings
from app.db.session import get_db
from app.schemas.finance import (
    FinanceAiAssessment,
    FinanceAiChatRequest,
    FinanceAiChatResponse,
    FinanceAiStatusResponse,
)
from app.services.finance_ai_advisor_service import finance_ai_advisor_service

router = APIRouter(prefix="/finance/ai", tags=["finance-ai"])


@router.get("/status", response_model=FinanceAiStatusResponse)
async def finance_ai_status(_: SessionData = Depends(require_admin)) -> FinanceAiStatusResponse:
    return FinanceAiStatusResponse(
        enabled=finance_ai_advisor_service.enabled,
        model=settings.ai_model if finance_ai_advisor_service.enabled else "",
        reason=finance_ai_advisor_service.status_reason(),
    )


def _require_enabled() -> None:
    if not finance_ai_advisor_service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=finance_ai_advisor_service.status_reason() or "Finance AI unavailable",
        )


@router.post("/assess", response_model=FinanceAiAssessment)
async def finance_ai_assess(
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FinanceAiAssessment:
    validate_csrf(request, session)
    _require_enabled()
    try:
        return await finance_ai_advisor_service.assess(db)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Finance AI assessment failed: {exc}",
        ) from exc


@router.post("/chat", response_model=FinanceAiChatResponse)
async def finance_ai_chat(
    body: FinanceAiChatRequest,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FinanceAiChatResponse:
    validate_csrf(request, session)
    _require_enabled()
    try:
        return await finance_ai_advisor_service.chat(db, body.messages)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Finance AI chat failed: {exc}",
        ) from exc
