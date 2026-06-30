from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.auth.passwords import StoredUser, get_seed_users, verify_password
from app.auth.sessions import CSRF_HEADER, SESSION_COOKIE, SessionData, session_manager
from app.schemas.domain import LoginRequest, UserInfo, UserRole


def authenticate_user(request: LoginRequest) -> StoredUser | None:
    users = get_seed_users()
    user = users.get(request.username)
    if not user or not verify_password(request.password, user.password_hash):
        return None
    return user


async def get_current_session(request: Request) -> SessionData:
    token = request.cookies.get(SESSION_COOKIE)
    session = session_manager.read_session(token)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return session


async def get_optional_session(request: Request) -> SessionData | None:
    token = request.cookies.get(SESSION_COOKIE)
    return session_manager.read_session(token)


async def require_viewer(session: SessionData = Depends(get_current_session)) -> SessionData:
    return session


async def require_admin(session: SessionData = Depends(get_current_session)) -> SessionData:
    if session.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return session


def validate_csrf(request: Request, session: SessionData) -> None:
    header_token = request.headers.get(CSRF_HEADER)
    if not header_token or header_token != session.csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def to_user_info(session: SessionData) -> UserInfo:
    return UserInfo(username=session.username, role=session.role)
