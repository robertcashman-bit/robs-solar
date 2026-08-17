from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_PREFIX = "/backend"


class StripBackendPrefixMiddleware(BaseHTTPMiddleware):
    """Accept /backend/* so hosted proxies can reach FastAPI without a path transform."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.scope.get("path") or ""
        if path == _PREFIX or path.startswith(f"{_PREFIX}/"):
            request.scope["path"] = path[len(_PREFIX) :] or "/"
            raw = request.scope.get("raw_path")
            if isinstance(raw, (bytes, bytearray)):
                prefix = _PREFIX.encode()
                if raw == prefix or raw.startswith(prefix + b"/"):
                    request.scope["raw_path"] = raw[len(prefix) :] or b"/"
        return await call_next(request)
