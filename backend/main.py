"""Vercel FastAPI entrypoint. The service root is backend/, so this file
must expose `app` at a default discovery path as well as app.main:app.
"""

from app.main import app

__all__ = ["app"]
