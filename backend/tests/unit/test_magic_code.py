"""Magic-code OTP and one-tap link auth tests."""

import time

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.auth.magic_code import magic_code_service
from app.config import settings
from app.db.models import AppSettingRow
from app.db.session import SessionLocal
from app.schemas.domain import UserRole


async def _clear_magic_rows() -> None:
    async with SessionLocal() as db:
        await db.execute(delete(AppSettingRow).where(AppSettingRow.key.like("auth.magic.%")))
        await db.commit()


@pytest.fixture(autouse=True)
def _reset_magic_codes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "magic_code_enabled", True)
    monkeypatch.setattr(settings, "magic_code_admin_emails", "rob@example.com")
    monkeypatch.setattr(settings, "magic_code_viewer_emails", "viewer@example.com")
    monkeypatch.setattr(settings, "admin_email", "robertdavidcashman@gmail.com")
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "public_app_url", "https://robs-solar.vercel.app")
    yield


def test_role_for_email() -> None:
    assert magic_code_service.role_for_email("rob@example.com") == UserRole.ADMIN
    assert magic_code_service.role_for_email("viewer@example.com") == UserRole.VIEWER
    assert magic_code_service.role_for_email("robertdavidcashman@gmail.com") == UserRole.ADMIN
    assert magic_code_service.role_for_email("other@example.com") is None


def test_admin_email_maps_to_admin_username() -> None:
    assert magic_code_service.username_for_email("robertdavidcashman@gmail.com") == "admin"


def test_public_app_origin_never_uses_tunnels(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings, "public_app_url", "https://battery-diff-des-higher.trycloudflare.com"
    )
    assert magic_code_service.public_app_origin() == "https://robs-solar.vercel.app"
    monkeypatch.setattr(settings, "public_app_url", "http://127.0.0.1:3000")
    assert magic_code_service.public_app_origin() == "https://robs-solar.vercel.app"
    monkeypatch.setattr(settings, "public_app_url", "https://robs-solar.vercel.app")
    assert magic_code_service.public_app_origin() == "https://robs-solar.vercel.app"


@pytest.mark.asyncio
async def test_request_and_verify_dev_code(client: AsyncClient) -> None:
    await _clear_magic_rows()
    status = await client.get("/auth/magic-code/status")
    assert status.status_code == 200
    assert status.json()["enabled"] is True
    assert status.json()["dev_delivery"] is True

    request = await client.post(
        "/auth/magic-code/request",
        json={"email": "rob@example.com"},
    )
    assert request.status_code == 200
    body = request.json()
    assert body["ok"] is True
    assert body["delivery"] == "dev"
    assert body["dev_code"]
    assert body["dev_link"].startswith("https://robs-solar.vercel.app/login?token=")
    assert "trycloudflare" not in body["dev_link"]
    first_code = body["dev_code"]

    again = await client.post(
        "/auth/magic-code/request",
        json={"email": "rob@example.com"},
    )
    assert again.status_code == 200
    second = again.json()
    assert second["dev_code"]
    assert second["dev_code"] != first_code
    assert second["dev_link"].startswith("https://robs-solar.vercel.app/login?token=")
    assert "6-digit" in second["message"].lower() or "shown below" in second["message"].lower()

    stale = await client.post(
        "/auth/magic-code/verify",
        json={"email": "rob@example.com", "code": first_code},
    )
    assert stale.status_code == 401

    verify = await client.post(
        "/auth/magic-code/verify",
        json={"email": "rob@example.com", "code": second["dev_code"]},
    )
    assert verify.status_code == 200
    data = verify.json()
    assert data["user"]["role"] == "admin"
    assert data["csrf_token"]

    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "rob"


@pytest.mark.asyncio
async def test_magic_link_consume_signs_in(client: AsyncClient) -> None:
    await _clear_magic_rows()
    request = await client.post(
        "/auth/magic-code/request",
        json={"email": "rob@example.com"},
    )
    token = request.json()["dev_link"].split("token=", 1)[1]
    consume = await client.post("/auth/magic-link/consume", json={"token": token})
    assert consume.status_code == 200
    assert consume.json()["user"]["role"] == "admin"
    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "rob"


@pytest.mark.asyncio
async def test_every_request_sends_a_new_email(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _clear_magic_rows()
    sent: list[str] = []

    async def fake_send(email: str, code: str, link: str) -> bool:
        sent.append(code)
        return True

    monkeypatch.setattr(settings, "resend_api_key", "re_test")
    monkeypatch.setattr(magic_code_service, "_send_code_email", fake_send)

    first = await client.post(
        "/auth/magic-code/request",
        json={"email": "rob@example.com"},
    )
    second = await client.post(
        "/auth/magic-code/request",
        json={"email": "rob@example.com"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["delivery"] == "email"
    assert second.json()["delivery"] == "email"
    assert len(sent) == 2
    assert sent[0] != sent[1]


@pytest.mark.asyncio
async def test_unknown_email_does_not_reveal(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/magic-code/request",
        json={"email": "unknown@example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body.get("dev_code") is None
    assert body.get("dev_link") is None


@pytest.mark.asyncio
async def test_invalid_code_rejected(client: AsyncClient) -> None:
    await _clear_magic_rows()
    await client.post("/auth/magic-code/request", json={"email": "rob@example.com"})
    bad = await client.post(
        "/auth/magic-code/verify",
        json={"email": "rob@example.com", "code": "000000"},
    )
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_expired_code_rejected(client: AsyncClient) -> None:
    await _clear_magic_rows()
    request = await client.post(
        "/auth/magic-code/request",
        json={"email": "rob@example.com"},
    )
    code = request.json()["dev_code"]
    record = await magic_code_service._load_record("rob@example.com")
    assert record is not None
    record["expires_at"] = time.time() - 1
    await magic_code_service._save_record("rob@example.com", record)

    expired = await client.post(
        "/auth/magic-code/verify",
        json={"email": "rob@example.com", "code": code},
    )
    assert expired.status_code == 401


@pytest.mark.asyncio
async def test_expired_link_rejected(client: AsyncClient) -> None:
    bad = await client.post(
        "/auth/magic-link/consume",
        json={"token": "this-is-not-a-real-signed-token"},
    )
    assert bad.status_code == 401
