from __future__ import annotations

import html
import logging

import httpx

from app.auth.magic_codes import code_hash, email_hash
from app.config import settings

logger = logging.getLogger(__name__)


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


async def send_magic_login_code(email: str, code: str) -> bool:
    api_key = (settings.resend_api_key or "").strip()
    from_email = (settings.resend_from_email or "").strip()
    if not api_key or not from_email:
        logger.warning("Magic-code email skipped — Resend is not configured")
        return False

    safe_code = _escape(code)
    payload = {
        "from": from_email,
        "to": [email],
        "subject": "Your Rob's Finance login code",
        "html": (
            '<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:20px">'
            '<h2 style="color:#0f172a;margin-bottom:8px">Your login code</h2>'
            '<p style="color:#475569;font-size:14px;margin-bottom:20px">'
            "Use this code to sign in to Rob's Finance. It expires in 10 minutes."
            "</p>"
            '<div style="background:#f8fafc;border:2px solid #e2e8f0;border-radius:8px;'
            'padding:24px;text-align:center;margin-bottom:20px">'
            f'<span style="font-family:monospace;font-size:32px;letter-spacing:0.3em;'
            f'font-weight:bold;color:#0f172a">{safe_code}</span>'
            "</div>"
            '<p style="color:#94a3b8;font-size:12px">'
            "If you didn&rsquo;t request this code, you can safely ignore this email."
            "</p>"
            "</div>"
        ),
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Idempotency-Key": f"magic-login/{email_hash(email)}/{code_hash(email, code)[:24]}",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError:
        logger.exception("Magic-code email request failed")
        return False

    if response.status_code >= 300:
        logger.warning("Magic-code email rejected status=%s", response.status_code)
        return False
    return True
