from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.config import settings
from app.db.models import MagicLoginCodeRow
from app.db.session import SessionLocal


@pytest.fixture(autouse=True)
async def clear_magic_codes() -> None:
    async with SessionLocal() as db:
        await db.execute(delete(MagicLoginCodeRow))
        await db.commit()


@pytest.fixture
def magic_admin(monkeypatch: pytest.MonkeyPatch) -> str:
    email = "admin@example.test"
    monkeypatch.setattr(settings, "magic_code_enabled", True)
    monkeypatch.setattr(settings, "magic_code_admin_emails", email)
    monkeypatch.setattr(settings, "admin_email", email)
    return email


@pytest.mark.asyncio
async def test_magic_request_unknown_email_does_not_send(
    client: AsyncClient,
    magic_admin: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send = AsyncMock(return_value=True)
    monkeypatch.setattr("app.routes.auth.send_magic_login_code", send)
    response = await client.post("/auth/magic/request", json={"email": "stranger@example.test"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_magic_request_and_verify(
    client: AsyncClient,
    magic_admin: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.routes.auth.generate_magic_code", lambda: "123456")
    send = AsyncMock(return_value=True)
    monkeypatch.setattr("app.routes.auth.send_magic_login_code", send)

    request = await client.post("/auth/magic/request", json={"email": magic_admin})
    assert request.status_code == 200
    send.assert_awaited_once()
    assert send.await_args.args[0] == magic_admin
    assert send.await_args.args[1] == "123456"

    wrong = await client.post(
        "/auth/magic/verify",
        json={"email": magic_admin, "code": "000000"},
    )
    assert wrong.status_code == 401

    verify = await client.post(
        "/auth/magic/verify",
        json={"email": magic_admin, "code": "123456"},
    )
    assert verify.status_code == 200
    body = verify.json()
    assert body["user"]["username"] == magic_admin
    assert body["user"]["role"] == "admin"
    assert body["csrf_token"]

    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == magic_admin


@pytest.mark.asyncio
async def test_magic_verify_unknown_email(
    client: AsyncClient,
    magic_admin: str,
) -> None:
    response = await client.post(
        "/auth/magic/verify",
        json={"email": "stranger@example.test", "code": "123456"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_magic_request_send_failure(
    client: AsyncClient,
    magic_admin: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.routes.auth.generate_magic_code", lambda: "654321")
    monkeypatch.setattr("app.routes.auth.send_magic_login_code", AsyncMock(return_value=False))
    response = await client.post("/auth/magic/request", json={"email": magic_admin})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_magic_disabled(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "magic_code_enabled", False)
    monkeypatch.setattr(settings, "magic_code_admin_emails", "admin@example.test")
    response = await client.post("/auth/magic/request", json={"email": "admin@example.test"})
    assert response.status_code == 503
