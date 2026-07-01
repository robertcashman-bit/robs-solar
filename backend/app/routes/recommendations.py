"""Optimisation recommendations — list, apply, dismiss."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin, require_viewer, validate_csrf
from app.auth.sessions import SessionData
from app.db.session import get_db
from app.middleware.rate_limit import enforce_write_rate_limit
from app.schemas.domain import RecommendationApplyResult, RecommendationsResponse
from app.services.recommendations_service import recommendations_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationsResponse)
async def list_recommendations(
    _: SessionData = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> RecommendationsResponse:
    return await recommendations_service.list_for_today(db)


@router.post("/{rec_id}/apply", response_model=RecommendationApplyResult)
async def apply_recommendation(
    rec_id: int,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> RecommendationApplyResult:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    return await recommendations_service.apply(
        db, rec_id, username=session.username, role=session.role
    )


@router.post("/{rec_id}/dismiss")
async def dismiss_recommendation(
    rec_id: int,
    request: Request,
    session: SessionData = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    validate_csrf(request, session)
    await enforce_write_rate_limit(request)
    ok = await recommendations_service.dismiss(db, rec_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return {"dismissed": True}
