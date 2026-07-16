import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import settings


class WriteRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.time()
        bucket = self._events[key]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Write rate limit exceeded",
            )
        bucket.append(now)


write_rate_limiter = WriteRateLimiter(settings.rate_limit_writes_per_minute)
# Separate, stricter bucket for credential stuffing (independent of write limit).
login_rate_limiter = WriteRateLimiter(max_requests=20, window_seconds=60)


async def enforce_write_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    write_rate_limiter.check(client_host)


async def enforce_login_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    try:
        login_rate_limiter.check(f"login:{client_host}")
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Login rate limit exceeded. Try again in a minute.",
        ) from exc
