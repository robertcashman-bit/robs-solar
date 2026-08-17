"""Cron bearer auth for the daily finance sync."""

import pytest
from fastapi import HTTPException

from app.auth.cron import require_cron_secret


def test_cron_secret_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.auth.cron.settings.cron_secret", "")
    with pytest.raises(HTTPException) as exc:
        require_cron_secret(authorization="Bearer anything")
    assert exc.value.status_code == 503


def test_cron_secret_rejects_wrong_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.auth.cron.settings.cron_secret", "expected")
    with pytest.raises(HTTPException) as exc:
        require_cron_secret(authorization="Bearer wrong")
    assert exc.value.status_code == 401


def test_cron_secret_accepts_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.auth.cron.settings.cron_secret", "expected")
    assert require_cron_secret(authorization="Bearer expected") is None
