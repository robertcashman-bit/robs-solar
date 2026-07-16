import pytest
from fastapi import HTTPException

from app.middleware.rate_limit import WriteRateLimiter, login_rate_limiter


def test_login_rate_limiter_blocks_after_max() -> None:
    limiter = WriteRateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        limiter.check("login:test-client")
    with pytest.raises(HTTPException) as exc:
        limiter.check("login:test-client")
    assert exc.value.status_code == 429


def test_module_login_rate_limiter_exists() -> None:
    assert login_rate_limiter.max_requests == 20
