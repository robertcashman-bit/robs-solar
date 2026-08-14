"""Accept /backend/* paths from the Vercel same-origin rewrite."""

from __future__ import annotations

PREFIX = "/backend"


class StripBackendPrefixMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in {"http", "websocket"}:
            path = scope.get("path", "")
            if path == PREFIX:
                scope = {**scope, "path": "/"}
            elif path.startswith(PREFIX + "/"):
                scope = {**scope, "path": path[len(PREFIX) :]}
        await self.app(scope, receive, send)
