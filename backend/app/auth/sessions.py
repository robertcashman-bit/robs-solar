import secrets
from dataclasses import dataclass
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings
from app.schemas.domain import UserRole

SESSION_COOKIE = "robs_solar_session"
CSRF_HEADER = "X-CSRF-Token"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12


@dataclass(frozen=True)
class SessionData:
    username: str
    role: UserRole
    csrf_token: str


class SessionManager:
    def __init__(self, secret_key: str) -> None:
        self._serializer = URLSafeTimedSerializer(secret_key, salt="robs-solar-session")

    def create_session_token(self, username: str, role: UserRole) -> tuple[str, str]:
        csrf_token = secrets.token_urlsafe(32)
        payload = {"username": username, "role": role.value, "csrf": csrf_token}
        return self._serializer.dumps(payload), csrf_token

    def read_session(self, token: Optional[str]) -> Optional[SessionData]:
        if not token:
            return None
        try:
            payload = self._serializer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
        except (BadSignature, SignatureExpired):
            return None
        return SessionData(
            username=payload["username"],
            role=UserRole(payload["role"]),
            csrf_token=payload["csrf"],
        )


session_manager = SessionManager(settings.secret_key)
