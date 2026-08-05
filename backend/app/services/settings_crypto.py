"""Encrypt sensitive app_settings values at rest using SECRET_KEY-derived Fernet."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)

_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal_text(plain: str) -> str:
    """Encrypt a UTF-8 string. Idempotent for already-sealed values."""
    if plain.startswith(_PREFIX):
        return plain
    token = _fernet().encrypt(plain.encode("utf-8")).decode("ascii")
    return f"{_PREFIX}{token}"


def open_text(value: str) -> str:
    """Decrypt a sealed string, or return plaintext for legacy unencrypted rows."""
    if not value.startswith(_PREFIX):
        return value
    token = value[len(_PREFIX) :]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt app_settings value — check SECRET_KEY continuity")
        raise


def seal_json(payload: dict[str, Any]) -> str:
    return seal_text(json.dumps(payload))


def open_json(value: str) -> dict[str, Any]:
    raw = open_text(value)
    data = json.loads(raw or "{}")
    if not isinstance(data, dict):
        return {}
    return data
