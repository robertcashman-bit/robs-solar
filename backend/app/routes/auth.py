from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth.dependencies import authenticate_user, get_current_session, to_user_info
from app.auth.sessions import SESSION_COOKIE, SessionData, session_manager
from app.config import settings
from app.middleware.rate_limit import enforce_login_rate_limit
from app.schemas.domain import LoginRequest, LoginResponse, SessionResponse, UserInfo

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response, request: Request) -> LoginResponse:
    await enforce_login_rate_limit(request)
    user = authenticate_user(body)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token, csrf_token = session_manager.create_session_token(user.username, user.role)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=60 * 60 * 12,
        path="/",
    )
    return LoginResponse(
        user=UserInfo(username=user.username, role=user.role),
        csrf_token=csrf_token,
    )


@router.post("/logout")
async def logout(
    response: Response,
    session: SessionData = Depends(get_current_session),
) -> dict[str, str]:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return {"status": "logged_out", "username": session.username}


@router.get("/me", response_model=SessionResponse)
async def me(session: SessionData = Depends(get_current_session)) -> SessionResponse:
    return SessionResponse(
        user=to_user_info(session),
        csrf_token=session.csrf_token,
    )
