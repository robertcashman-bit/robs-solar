from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse

from app.auth.dependencies import authenticate_user, get_current_session, to_user_info
from app.auth.magic_code import MagicCodeError, magic_code_service
from app.auth.oidc import (
    OidcAuthError,
    OidcNotConfiguredError,
    build_login_redirect,
    create_state,
    exchange_code,
    fetch_userinfo,
    map_user_from_claims,
    oidc_configured,
    verify_state,
)
from app.auth.sessions import SESSION_COOKIE, SessionData, session_manager
from app.config import settings
from app.schemas.domain import (
    LoginRequest,
    LoginResponse,
    MagicCodeRequest,
    MagicCodeRequestResponse,
    MagicCodeStatusResponse,
    MagicCodeVerifyRequest,
    MagicLinkConsumeRequest,
    SessionResponse,
    UserInfo,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _frontend_redirect(path: str = "/") -> str:
    origins = settings.cors_origin_list
    base = origins[0] if origins else "http://127.0.0.1:3000"
    return f"{base.rstrip('/')}{path}"


def _set_session_cookie(response: Response, username: str, role) -> str:
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
    return csrf_token


@router.get("/oidc/status")
async def oidc_status() -> dict[str, bool]:
    return {"enabled": oidc_configured()}


@router.get("/oidc/login")
async def oidc_login() -> RedirectResponse:
    if not oidc_configured():
        raise HTTPException(status_code=404, detail="OIDC is not enabled")
    state = create_state()
    try:
        url = await build_login_redirect(state)
    except OidcAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/oidc/callback")
async def oidc_callback(
    response: Response,
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    if not oidc_configured():
        raise HTTPException(status_code=404, detail="OIDC is not enabled")
    try:
        verify_state(state)
        tokens = await exchange_code(code)
        access_token = str(tokens.get("access_token", ""))
        if not access_token:
            raise OidcAuthError("OIDC token response missing access_token")
        claims = await fetch_userinfo(access_token)
        username, role = map_user_from_claims(claims)
    except (OidcAuthError, OidcNotConfiguredError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _set_session_cookie(response, username, role)
    return RedirectResponse(url=_frontend_redirect("/"), status_code=status.HTTP_302_FOUND)


@router.get("/magic-code/status", response_model=MagicCodeStatusResponse)
async def magic_code_status() -> MagicCodeStatusResponse:
    return MagicCodeStatusResponse(
        enabled=magic_code_service.enabled(),
        password_login_enabled=True,
        email_delivery_configured=magic_code_service.email_delivery_configured(),
        dev_delivery=magic_code_service.dev_delivery(),
    )


@router.post("/magic-code/request", response_model=MagicCodeRequestResponse)
async def magic_code_request(body: MagicCodeRequest) -> MagicCodeRequestResponse:
    try:
        result = await magic_code_service.request_code(body.email)
    except MagicCodeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return MagicCodeRequestResponse.model_validate(result)


@router.post("/magic-link/consume", response_model=LoginResponse)
async def magic_link_consume(
    body: MagicLinkConsumeRequest,
    response: Response,
) -> LoginResponse:
    try:
        username, role = await magic_code_service.consume_link(body.token)
    except MagicCodeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    csrf_token = _set_session_cookie(response, username, role)
    return LoginResponse(
        user=UserInfo(username=username, role=role),
        csrf_token=csrf_token,
    )


@router.post("/magic-code/verify", response_model=LoginResponse)
async def magic_code_verify(
    body: MagicCodeVerifyRequest,
    response: Response,
) -> LoginResponse:
    try:
        username, role = await magic_code_service.verify_code(body.email, body.code)
    except MagicCodeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    csrf_token = _set_session_cookie(response, username, role)
    return LoginResponse(
        user=UserInfo(username=username, role=role),
        csrf_token=csrf_token,
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response) -> LoginResponse:
    user = authenticate_user(request)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    csrf_token = _set_session_cookie(response, user.username, user.role)
    return LoginResponse(
        user=UserInfo(username=user.username, role=user.role),
        csrf_token=csrf_token,
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return {"status": "logged_out"}


@router.get("/me", response_model=SessionResponse)
async def me(session: SessionData = Depends(get_current_session)) -> SessionResponse:
    return SessionResponse(
        user=to_user_info(session),
        csrf_token=session.csrf_token,
    )
