from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import MagicLoginCodeRow
from app.schemas.domain import UserRole

MAGIC_CODE_TTL = timedelta(minutes=10)
MAGIC_CODE_COOLDOWN = timedelta(seconds=30)
MAX_VERIFY_ATTEMPTS = 5


@dataclass(frozen=True)
class MagicLoginUser:
    username: str
    role: UserRole


def normalize_email(email: str) -> str:
    return email.strip().lower()


def generate_magic_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_magic_value(value: str) -> str:
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def email_hash(email: str) -> str:
    return hash_magic_value(f"magic-email:{normalize_email(email)}")


def code_hash(email: str, code: str) -> str:
    return hash_magic_value(f"magic-code:{normalize_email(email)}:{code}")


def resolve_magic_login_user(email: str) -> MagicLoginUser | None:
    normalized = normalize_email(email)
    if normalized in settings.magic_code_admin_email_set:
        return MagicLoginUser(username=normalized, role=UserRole.ADMIN)
    return None


def magic_code_is_configured() -> bool:
    return bool(settings.magic_code_enabled and settings.magic_code_admin_email_set)


async def store_magic_code(db: AsyncSession, email: str, code: str) -> bool:
    """Persist a hashed code. Returns False when a recent code is still cooling down."""
    now = datetime.now(timezone.utc)
    key = email_hash(email)
    existing = await db.get(MagicLoginCodeRow, key)
    if existing is not None:
        created = existing.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if now - created < MAGIC_CODE_COOLDOWN:
            return False
        existing.code_hash = code_hash(email, code)
        existing.expires_at = now + MAGIC_CODE_TTL
        existing.attempts = 0
        existing.created_at = now
    else:
        db.add(
            MagicLoginCodeRow(
                email_hash=key,
                code_hash=code_hash(email, code),
                expires_at=now + MAGIC_CODE_TTL,
                attempts=0,
                created_at=now,
            )
        )
    await db.commit()
    return True


async def verify_magic_code(db: AsyncSession, email: str, code: str) -> str | None:
    """Return None on success, or a user-facing error string."""
    now = datetime.now(timezone.utc)
    row = await db.get(MagicLoginCodeRow, email_hash(email))
    if row is None:
        return "Code expired or not found. Please request a new one."

    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        await db.delete(row)
        await db.commit()
        return "Code expired or not found. Please request a new one."

    if row.attempts >= MAX_VERIFY_ATTEMPTS:
        await db.delete(row)
        await db.commit()
        return "Too many attempts. Please request a new code."

    expected = row.code_hash.encode("utf-8")
    actual = code_hash(email, code).encode("utf-8")
    if len(expected) != len(actual) or not hmac.compare_digest(expected, actual):
        row.attempts += 1
        await db.commit()
        if row.attempts >= MAX_VERIFY_ATTEMPTS:
            await db.delete(row)
            await db.commit()
            return "Too many attempts. Please request a new code."
        return "Incorrect code. Please try again."

    await db.delete(row)
    await db.commit()
    return None
