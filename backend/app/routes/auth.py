from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import authenticate_user, get_current_session, to_user_info
from app.auth.magic_codes import (
    generate_magic_code,
    magic_code_is_configured,
    resolve_magic_login_user,
    store_magic_code,
    verify_magic_code,
)
from app.auth.sessions import SESSION_COOKIE, SessionData, session_manager
from app.config import settings
from app.db.session import get_db
from app.middleware.rate_limit import enforce_login_rate_limit
from app.schemas.domain import (
    LoginRequest,
    LoginResponse,
    MagicLoginRequest,
    MagicLoginRequestResponse,
    MagicLoginVerifyRequest,
    SessionResponse,
    UserInfo,
    UserRole,
)
from app.services.magic_login_email import send_magic_login_code

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_session(response: Response, username: str, role: UserRole) -> LoginResponse:
    token, csrf_token = session_manager.create_session_token(username, role)
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
        user=UserInfo(username=username, role=role),
        csrf_token=csrf_token,
    )


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response, request: Request) -> LoginResponse:
    await enforce_login_rate_limit(request)
    user = authenticate_user(body)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return _issue_session(response, user.username, user.role)


@router.post("/magic/request", response_model=MagicLoginRequestResponse)
async def request_magic_code(
    body: MagicLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MagicLoginRequestResponse:
    await enforce_login_rate_limit(request)
    if not magic_code_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Magic-code sign-in is not configured",
        )
    user = resolve_magic_login_user(body.email)
    if user is None:
        return MagicLoginRequestResponse(ok=True)

    code = generate_magic_code()
    stored = await store_magic_code(db, body.email, code)
    if stored:
        sent = await send_magic_login_code(body.email, code)
        if not sent:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not send the login code. Try again shortly.",
            )
    return MagicLoginRequestResponse(ok=True)


@router.post("/magic/verify", response_model=LoginResponse)
async def verify_magic_login(
    body: MagicLoginVerifyRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    await enforce_login_rate_limit(request)
    user = resolve_magic_login_user(body.email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")
    error = await verify_magic_code(db, body.email, body.code)
    if error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error)
    return _issue_session(response, user.username, user.role)


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
