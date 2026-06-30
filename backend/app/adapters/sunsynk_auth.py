"""Sunsynk Connect authentication helpers.

Reverse-engineered from the official www.sunsynk.net web app (Nov 2024+ flow).
The API requires nonce + MD5 sign + RSA-encrypted password. This is UNVERIFIED
third-party integration but matches the live website login sequence.
"""

from __future__ import annotations

import base64
import hashlib
import time
from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

SOURCE = "sunsynk"
PUBLIC_KEY_PATH = "/anonymous/publicKey"
TOKEN_PATH = "/oauth/token/new"
PUBLIC_KEY_SIGN_SALT = "POWER_VIEW"


def md5_hex(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def _nonce_ms() -> int:
    return int(time.time() * 1000)


def public_key_query(nonce: int, source: str = SOURCE) -> str:
    return f"nonce={nonce}&source={source}"


def sign_for_public_key(nonce: int, source: str = SOURCE) -> str:
    return md5_hex(public_key_query(nonce, source) + PUBLIC_KEY_SIGN_SALT)


def sign_for_login(nonce: int, public_key: str, source: str = SOURCE) -> str:
    return md5_hex(public_key_query(nonce, source) + public_key[:10])


def encrypt_password_rsa(plain_password: str, public_key: str) -> str:
    key_material = public_key.strip()
    if "BEGIN PUBLIC KEY" not in key_material:
        key_material = f"-----BEGIN PUBLIC KEY-----\n{key_material}\n-----END PUBLIC KEY-----"
    key = serialization.load_pem_public_key(key_material.encode("utf-8"))
    encrypted = key.encrypt(plain_password.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode("ascii")


async def fetch_public_key(client: httpx.AsyncClient, source: str = SOURCE) -> str:
    nonce = _nonce_ms()
    query = public_key_query(nonce, source)
    sign = sign_for_public_key(nonce, source)
    response = await client.get(f"{PUBLIC_KEY_PATH}?{query}&sign={sign}")
    response.raise_for_status()
    body = response.json()
    if not body.get("success"):
        raise ValueError(body.get("msg") or "Failed to fetch Sunsynk public key")
    data = body.get("data")
    if not isinstance(data, str) or not data:
        raise ValueError("Sunsynk public key response missing data")
    return data


async def login(
    client: httpx.AsyncClient,
    *,
    username: str,
    plain_password: str,
    source: str = SOURCE,
) -> dict[str, Any]:
    public_key = await fetch_public_key(client, source)
    nonce = _nonce_ms()
    sign = sign_for_login(nonce, public_key, source)
    encrypted_password = encrypt_password_rsa(plain_password, public_key)
    payload = {
        "sign": sign,
        "nonce": nonce,
        "username": username,
        "password": encrypted_password,
        "grant_type": "password",
        "client_id": "csp-web",
        "source": source,
        "areaCode": source,
    }
    response = await client.post(TOKEN_PATH, json=payload)
    response.raise_for_status()
    body = response.json()
    if not body.get("success"):
        raise ValueError(body.get("msg") or "Sunsynk login failed")
    data = body.get("data") or {}
    token = data.get("access_token")
    if not token:
        raise ValueError("Sunsynk login returned no access token")
    return data
