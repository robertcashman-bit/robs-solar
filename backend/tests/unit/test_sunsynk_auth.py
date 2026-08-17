import json

import httpx
import pytest

from app.adapters.sunsynk_auth import (
    SunsynkVerificationRequired,
    encrypt_password_rsa,
    login,
    sign_for_login,
    sign_for_public_key,
)

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu1SU1LfVLPHCozMxH2Mo
4mHlMNbcvHAbX5e1dH7mM8g0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k
0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6
k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n
6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k
0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n
6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k0n6k
0wIDAQAB
-----END PUBLIC KEY-----"""


def test_public_key_sign_uses_power_view_salt() -> None:
    assert sign_for_public_key(1234567890) == sign_for_public_key(1234567890)
    assert sign_for_public_key(1234567890) != sign_for_login(1234567890, "abcdefghij")


def test_login_sign_uses_public_key_prefix() -> None:
    nonce = 999
    key = "abcdefghijklmnop"
    assert sign_for_login(nonce, key) != sign_for_login(nonce, "klmnopqrst")


def test_encrypt_password_returns_base64() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    encrypted = encrypt_password_rsa("test-pass", public_pem)
    assert encrypted
    assert encrypted != "test-pass"


def _login_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="https://api.test",
        transport=httpx.MockTransport(handler),
        timeout=5.0,
    )


_LOGIN_PRIVATE_KEY = None


def _login_public_key_pem() -> str:
    global _LOGIN_PRIVATE_KEY
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    if _LOGIN_PRIVATE_KEY is None:
        _LOGIN_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        _LOGIN_PRIVATE_KEY.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )


def _public_key_handler(request: httpx.Request, token_body: dict) -> httpx.Response:
    if request.url.path == "/anonymous/publicKey":
        return httpx.Response(200, json={"success": True, "data": _login_public_key_pem()})
    if request.url.path == "/oauth/token/new":
        return httpx.Response(200, json=token_body)
    return httpx.Response(404)


@pytest.mark.asyncio
async def test_login_lockout_raises_verification_required() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _public_key_handler(
            request,
            {
                "success": False,
                "msg": "Too many login failures, please enter the verification code!",
            },
        )

    with pytest.raises(SunsynkVerificationRequired, match="verification code"):
        await login(
            _login_client(handler),
            username="user@example.com",
            plain_password="secret",
        )


@pytest.mark.asyncio
async def test_login_includes_verify_code_when_set() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token/new":
            captured.update(json.loads(request.content.decode()))
        return _public_key_handler(
            request,
            {"success": True, "data": {"access_token": "tok-123", "expires_in": 3600}},
        )

    data = await login(
        _login_client(handler),
        username="user@example.com",
        plain_password="secret",
        verify_code="482913",
    )
    assert data["access_token"] == "tok-123"
    assert captured["verifyCode"] == "482913"
    assert "secret" not in json.dumps(captured)


@pytest.mark.asyncio
async def test_login_omits_verify_code_when_unset() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token/new":
            captured.update(json.loads(request.content.decode()))
        return _public_key_handler(
            request,
            {"success": True, "data": {"access_token": "tok-123", "expires_in": 3600}},
        )

    await login(
        _login_client(handler),
        username="user@example.com",
        plain_password="secret",
    )
    assert "verifyCode" not in captured
