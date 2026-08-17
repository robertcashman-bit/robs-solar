from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.auth.magic_codes import (
    code_hash,
    generate_magic_code,
    hash_magic_value,
    magic_code_is_configured,
    normalize_email,
    resolve_magic_login_user,
    store_magic_code,
    verify_magic_code,
)
from app.config import settings
from app.db.models import MagicLoginCodeRow
from app.db.session import SessionLocal
from app.schemas.domain import UserRole


def test_generate_magic_code_is_six_digits() -> None:
    code = generate_magic_code()
    assert len(code) == 6
    assert code.isdigit()


def test_hash_is_stable_and_secret_dependent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "secret_key", "alpha")
    first = hash_magic_value("payload")
    second = hash_magic_value("payload")
    assert first == second
    monkeypatch.setattr(settings, "secret_key", "beta")
    assert hash_magic_value("payload") != first


def test_code_hash_differs_by_email() -> None:
    assert code_hash("a@example.com", "123456") != code_hash("b@example.com", "123456")


def test_resolve_admin_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "magic_code_admin_emails", "rob@example.com, other@example.com")
    monkeypatch.setattr(settings, "admin_email", "")
    user = resolve_magic_login_user("Rob@example.com")
    assert user is not None
    assert user.role == UserRole.ADMIN
    assert user.username == "rob@example.com"
    assert resolve_magic_login_user("stranger@example.com") is None


def test_admin_email_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "magic_code_admin_emails", "")
    monkeypatch.setattr(settings, "admin_email", "owner@example.com")
    user = resolve_magic_login_user("owner@example.com")
    assert user is not None
    assert user.username == "owner@example.com"


def test_magic_code_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "magic_code_enabled", True)
    monkeypatch.setattr(settings, "magic_code_admin_emails", "rob@example.com")
    assert magic_code_is_configured() is True
    monkeypatch.setattr(settings, "magic_code_enabled", False)
    assert magic_code_is_configured() is False


def test_normalize_email() -> None:
    assert normalize_email("  Rob@Example.COM ") == "rob@example.com"


@pytest.mark.asyncio
async def test_store_and_verify_magic_code() -> None:
    async with SessionLocal() as db:
        await db.execute(delete(MagicLoginCodeRow))
        await db.commit()
        stored = await store_magic_code(db, "store@example.test", "123456")
        assert stored is True
        assert await verify_magic_code(db, "store@example.test", "000000") == (
            "Incorrect code. Please try again."
        )
        assert await verify_magic_code(db, "store@example.test", "123456") is None
        assert await verify_magic_code(db, "store@example.test", "123456") == (
            "Code expired or not found. Please request a new one."
        )
