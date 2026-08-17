"""Email a fresh 6-digit magic code on every sign-in request."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import delete

from app.config import settings
from app.db.models import AppSettingRow
from app.db.session import SessionLocal
from app.schemas.domain import UserRole

logger = logging.getLogger(__name__)

_CODE_LENGTH = 6
_MAX_ATTEMPTS = 8
_PUBLIC_APP_URL = "https://robs-solar.vercel.app"
_LINK_SALT = "robs-finance-magic-link"
_SETTING_PREFIX = "auth.magic."


class MagicCodeError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


class MagicCodeService:
    def enabled(self) -> bool:
        return bool(settings.magic_code_enabled)

    def email_delivery_configured(self) -> bool:
        return bool(settings.resend_api_key.strip())

    def dev_delivery(self) -> bool:
        return not self.email_delivery_configured() and not settings.is_production

    def role_for_email(self, email: str) -> UserRole | None:
        normalized = email.strip().lower()
        if not normalized or "@" not in normalized:
            return None
        if normalized in settings.magic_code_admin_email_list:
            return UserRole.ADMIN
        if normalized in settings.magic_code_viewer_email_list:
            return UserRole.VIEWER
        return None

    def username_for_email(self, email: str) -> str:
        normalized = email.strip().lower()
        if normalized == settings.admin_email.strip().lower():
            return settings.admin_username
        if normalized == settings.admin_username.strip().lower():
            return settings.admin_username
        local = normalized.split("@", 1)[0]
        return local.replace(".", "-")[:64] or "user"

    def public_app_origin(self) -> str:
        configured = settings.public_app_url.strip().rstrip("/")
        parsed = urlparse(configured)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme == "https"
            and host
            and not host.endswith("trycloudflare.com")
            and host != "localhost"
        ):
            return f"https://{host}" if parsed.port in {None, 443} else configured
        return _PUBLIC_APP_URL

    def public_sign_in_url(self, token: str) -> str:
        return f"{self.public_app_origin()}/login?token={token}"

    def _link_serializer(self) -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(settings.secret_key, salt=_LINK_SALT)

    def issue_link_token(self, email: str, username: str, role: UserRole) -> str:
        return self._link_serializer().dumps(
            {"email": email, "username": username, "role": role.value}
        )

    def _ttl_seconds(self) -> int:
        return max(60, int(settings.magic_code_ttl_seconds))

    def _setting_key(self, email: str) -> str:
        digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:32]
        return f"{_SETTING_PREFIX}{digest}"

    def _new_code(self) -> str:
        return f"{secrets.randbelow(10**_CODE_LENGTH):0{_CODE_LENGTH}d}"

    def _hash_code(self, email: str, code: str) -> str:
        return hmac.new(
            settings.secret_key.encode("utf-8"),
            f"{email.strip().lower()}:{code}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _hashes_match(self, email: str, code: str, stored_hash: str) -> bool:
        expected = self._hash_code(email, code)
        return hmac.compare_digest(expected, stored_hash)

    async def _load_record(self, email: str) -> dict[str, Any] | None:
        key = self._setting_key(email)
        async with SessionLocal() as db:
            row = await db.get(AppSettingRow, key)
            if row is None:
                return None
            try:
                payload = json.loads(row.value)
            except json.JSONDecodeError:
                return None
        return payload if isinstance(payload, dict) else None

    async def _save_record(self, email: str, record: dict[str, Any]) -> None:
        key = self._setting_key(email)
        payload = json.dumps(record)
        async with SessionLocal() as db:
            row = await db.get(AppSettingRow, key)
            if row is None:
                db.add(AppSettingRow(key=key, value=payload))
            else:
                row.value = payload
            await db.commit()

    async def _delete_record(self, email: str) -> None:
        key = self._setting_key(email)
        async with SessionLocal() as db:
            await db.execute(delete(AppSettingRow).where(AppSettingRow.key == key))
            await db.commit()

    async def request_code(self, email: str) -> dict[str, object]:
        if not self.enabled():
            raise MagicCodeError("Magic-code sign-in is disabled", status_code=404)

        normalized = email.strip().lower()
        role = self.role_for_email(normalized)
        generic = {
            "ok": True,
            "message": "If that email is allowed, a new sign-in code has been sent.",
            "expires_in_seconds": self._ttl_seconds(),
            "delivery": "email" if self.email_delivery_configured() else "dev",
        }
        if role is None:
            return generic

        username = self.username_for_email(normalized)
        token = self.issue_link_token(normalized, username, role)
        link = self.public_sign_in_url(token)
        code = self._new_code()
        now = time.time()
        record = {
            "hash": self._hash_code(normalized, code),
            "expires_at": now + self._ttl_seconds(),
            "attempts": 0,
        }
        await self._save_record(normalized, record)

        sent = await self._send_code_email(normalized, code, link)
        if not sent and settings.is_production:
            await self._delete_record(normalized)
            raise MagicCodeError(
                "Unable to send sign-in email. Check RESEND_API_KEY configuration.",
                status_code=503,
            )

        payload = dict(generic)
        if sent:
            payload["message"] = (
                "A new 6-digit sign-in code is on its way. "
                "It replaces any previous code."
            )
            payload["delivery"] = "email"
        else:
            payload["message"] = (
                "Use the new 6-digit code shown below "
                "(email delivery is not configured)."
            )
            payload["delivery"] = "dev"
            payload["dev_code"] = code
            payload["dev_link"] = link
            logger.warning("Magic code for %s (dev only): %s", normalized, code)
        return payload

    async def verify_code(self, email: str, code: str) -> tuple[str, UserRole]:
        if not self.enabled():
            raise MagicCodeError("Magic-code sign-in is disabled", status_code=404)

        normalized = email.strip().lower()
        role = self.role_for_email(normalized)
        cleaned = "".join(ch for ch in code.strip() if ch.isdigit())
        if role is None or len(cleaned) != _CODE_LENGTH:
            raise MagicCodeError("Invalid or expired code", status_code=401)

        record = await self._load_record(normalized)
        if record is None:
            raise MagicCodeError("Invalid or expired code", status_code=401)

        expires_at = float(record.get("expires_at") or 0)
        if expires_at < time.time():
            await self._delete_record(normalized)
            raise MagicCodeError("Invalid or expired code", status_code=401)

        attempts = int(record.get("attempts") or 0) + 1
        record["attempts"] = attempts
        if attempts > _MAX_ATTEMPTS:
            await self._delete_record(normalized)
            raise MagicCodeError("Too many attempts. Request a new code.", status_code=429)

        stored_hash = str(record.get("hash") or "")
        if not stored_hash or not self._hashes_match(normalized, cleaned, stored_hash):
            await self._save_record(normalized, record)
            raise MagicCodeError("Invalid or expired code", status_code=401)

        await self._delete_record(normalized)
        return self.username_for_email(normalized), role

    async def consume_link(self, token: str) -> tuple[str, UserRole]:
        if not self.enabled():
            raise MagicCodeError("Magic-code sign-in is disabled", status_code=404)
        cleaned = token.strip()
        if not cleaned:
            raise MagicCodeError("Invalid or expired sign-in link", status_code=401)
        try:
            payload = self._link_serializer().loads(
                cleaned, max_age=self._ttl_seconds()
            )
        except (BadSignature, SignatureExpired) as exc:
            raise MagicCodeError(
                "Invalid or expired sign-in link", status_code=401
            ) from exc
        email = str(payload.get("email", "")).strip().lower()
        role = self.role_for_email(email)
        if role is None:
            raise MagicCodeError("Invalid or expired sign-in link", status_code=401)
        username = str(payload.get("username") or self.username_for_email(email))
        return username, role

    async def _send_code_email(self, email: str, code: str, link: str) -> bool:
        if not settings.resend_api_key:
            return False
        minutes = max(1, self._ttl_seconds() // 60)
        subject = "Your Rob's Finance sign-in code"
        text = (
            f"Your Rob's Finance sign-in code is: {code}\n\n"
            f"It expires in {minutes} minutes. Requesting a new code replaces this one.\n\n"
            f"You can also tap this link to sign in: {link}\n"
            "If you did not request this, ignore the email."
        )
        html = (
            "<div style=\"font-family:Arial,sans-serif;max-width:520px;"
            "margin:0 auto;padding:24px;color:#0f172a\">"
            "<h1 style=\"margin:0 0 12px;font-size:22px\">"
            "Your sign-in code</h1>"
            "<p style=\"margin:0 0 16px;color:#334155\">"
            f"Enter this 6-digit code to sign in to Rob's Finance. "
            f"It expires in {minutes} minutes and replaces any earlier code.</p>"
            "<div style=\"font-size:32px;letter-spacing:8px;font-weight:700;"
            "background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;"
            f"padding:16px;text-align:center\">{code}</div>"
            "<p style=\"margin:24px 0 12px;color:#64748b;font-size:13px\">"
            "Or tap the button to open the live app already signed in.</p>"
            "<p style=\"margin:0 0 8px;text-align:center\">"
            f"<a href=\"{link}\" style=\"display:inline-block;background:#0f766e;"
            "color:#ffffff;text-decoration:none;font-weight:700;"
            "padding:14px 28px;border-radius:10px\">Sign in</a></p>"
            "<p style=\"margin:16px 0 0;color:#64748b;font-size:13px\">"
            "If you did not request this, ignore the email.</p></div>"
        )
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {settings.resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": settings.resend_from_email,
                        "to": [email],
                        "subject": subject,
                        "text": text,
                        "html": html,
                    },
                )
            if response.status_code >= 400:
                logger.error("Resend magic-code email failed: %s", response.text)
                return False
            return True
        except httpx.HTTPError as exc:
            logger.error("Resend magic-code email error: %s", exc)
            return False


magic_code_service = MagicCodeService()
