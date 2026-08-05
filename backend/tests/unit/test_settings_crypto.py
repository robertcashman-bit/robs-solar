"""Tests for app_settings encryption helpers."""

from __future__ import annotations

from app.services.settings_crypto import open_json, open_text, seal_json, seal_text


def test_seal_text_round_trip() -> None:
    sealed = seal_text("secret-value")
    assert sealed.startswith("enc:v1:")
    assert open_text(sealed) == "secret-value"


def test_seal_text_idempotent() -> None:
    sealed = seal_text("once")
    assert seal_text(sealed) == sealed


def test_open_text_accepts_legacy_plaintext() -> None:
    assert open_text('{"api_key":"plain"}') == '{"api_key":"plain"}'


def test_seal_json_round_trip() -> None:
    payload = {"api_key": "lf-test-key", "extra": 1}
    sealed = seal_json(payload)
    assert sealed.startswith("enc:v1:")
    assert open_json(sealed) == payload
