import logging
from dataclasses import dataclass

import bcrypt

from app.config import settings
from app.schemas.domain import UserRole

logger = logging.getLogger(__name__)

_DEFAULT_PASSWORDS = frozenset({"change-me-admin", "change-me-viewer"})


@dataclass(frozen=True)
class StoredUser:
    username: str
    role: UserRole
    password_hash: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def _login_key(value: str) -> str:
    return value.strip().lower()


def get_seed_users() -> dict[str, StoredUser]:
    admin = StoredUser(
        username=settings.admin_username,
        role=UserRole.ADMIN,
        password_hash=hash_password(settings.admin_password),
    )
    viewer = StoredUser(
        username=settings.viewer_username,
        role=UserRole.VIEWER,
        password_hash=hash_password(settings.viewer_password),
    )
    users = {
        _login_key(settings.admin_username): admin,
        _login_key(settings.viewer_username): viewer,
    }
    admin_email = _login_key(settings.admin_email)
    if admin_email:
        users[admin_email] = admin
    return users


def uses_default_passwords() -> bool:
    return (
        settings.admin_password in _DEFAULT_PASSWORDS
        or settings.viewer_password in _DEFAULT_PASSWORDS
    )


def warn_if_default_passwords() -> None:
    if uses_default_passwords():
        logger.warning(
            "Default admin/viewer passwords detected — change ADMIN_PASSWORD and "
            "VIEWER_PASSWORD in backend/.env before exposing this service to a network."
        )
