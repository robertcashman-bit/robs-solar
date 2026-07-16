import pytest

from app.auth.passwords import assert_production_secret_key
from app.config import settings


def test_assert_production_secret_key_allows_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "secret_key", "change-me")
    assert_production_secret_key()


def test_assert_production_secret_key_rejects_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "secret_key", "change-me")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        assert_production_secret_key()


def test_assert_production_secret_key_allows_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "secret_key", "a-sufficiently-long-random-production-secret")
    assert_production_secret_key()
