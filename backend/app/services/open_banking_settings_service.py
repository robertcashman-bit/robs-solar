"""Open Banking credential and connection settings."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettingRow
from app.integrations.open_banking.factory import is_connection_linked
from app.schemas.finance import (
    OpenBankingConfig,
    OpenBankingConfigStatus,
    OpenBankingRequisition,
)
from app.services.open_banking_readiness import probe_provider_readiness
from app.services.settings_crypto import open_json, seal_json

_OPEN_BANKING_KEY = "open_banking"
_REQUISITIONS_KEY = "open_banking_requisitions"
_PENDING_KEY = "open_banking_pending"
_LAST_SYNC_KEY = "open_banking_last_sync_at"


class OpenBankingSettingsService:
    def _read_private_key_pem(self) -> str:
        inline = settings.enable_banking_private_key_pem.strip()
        if inline:
            return inline.replace("\\n", "\n")
        path = settings.enable_banking_private_key_path.strip()
        if path:
            key_path = Path(path)
            if key_path.is_file():
                return key_path.read_text(encoding="utf-8")
        return ""

    def _env_config(self) -> OpenBankingConfig:
        provider = settings.open_banking_provider.strip().lower()
        if provider not in ("enable_banking", "gocardless"):
            provider = "enable_banking"
        env_value = settings.enable_banking_environment.strip().upper()
        environment = env_value if env_value in ("SANDBOX", "PRODUCTION") else "SANDBOX"
        return OpenBankingConfig(
            provider=provider,  # type: ignore[arg-type]
            application_id=settings.enable_banking_application_id,
            private_key_pem=self._read_private_key_pem(),
            environment=environment,  # type: ignore[arg-type]
            secret_id=settings.open_banking_secret_id,
            secret_key=settings.open_banking_secret_key,
            redirect_url=settings.open_banking_redirect_url,
        )

    def _merge_config(self, stored: OpenBankingConfig, env: OpenBankingConfig) -> OpenBankingConfig:
        provider = stored.provider or env.provider
        # Hosted deploys may have ephemeral SQLite — prefer explicit env credentials.
        env_has_credentials = bool(env.application_id and env.private_key_pem)
        application_id = (
            env.application_id
            if env_has_credentials
            else (stored.application_id or env.application_id)
        )
        private_key_pem = (
            env.private_key_pem
            if env_has_credentials
            else (stored.private_key_pem or env.private_key_pem)
        )
        environment = (
            env.environment if env_has_credentials else (stored.environment or env.environment)
        )
        redirect_url = (
            env.redirect_url if env_has_credentials else (stored.redirect_url or env.redirect_url)
        )
        return OpenBankingConfig(
            provider=provider,
            application_id=application_id,
            private_key_pem=private_key_pem,
            environment=environment,
            secret_id=stored.secret_id or env.secret_id,
            secret_key=stored.secret_key or env.secret_key,
            redirect_url=redirect_url,
            access_token=stored.access_token or env.access_token,
            refresh_token=stored.refresh_token or env.refresh_token,
            access_expires_at=stored.access_expires_at or env.access_expires_at,
        )

    def is_configured(self, config: OpenBankingConfig) -> bool:
        if config.provider == "gocardless":
            return bool(config.secret_id and config.secret_key)
        return bool(config.application_id and config.private_key_pem)

    async def _get_row(self, db: AsyncSession, key: str) -> AppSettingRow | None:
        return await db.scalar(select(AppSettingRow).where(AppSettingRow.key == key))

    async def get_config(self, db: AsyncSession) -> OpenBankingConfig:
        row = await self._get_row(db, _OPEN_BANKING_KEY)
        env = self._env_config()
        if row is None:
            return env
        stored = OpenBankingConfig.model_validate(open_json(row.value))
        return self._merge_config(stored, env)

    async def save_tokens(
        self,
        db: AsyncSession,
        *,
        access_token: str | None,
        refresh_token: str | None,
        access_expires_at: datetime | None,
    ) -> None:
        config = await self.get_config(db)
        if config.provider != "gocardless":
            return
        if access_token:
            config.access_token = access_token
        if refresh_token:
            config.refresh_token = refresh_token
        if access_expires_at:
            config.access_expires_at = access_expires_at
        await self.set_config(db, config)

    async def get_status(self, db: AsyncSession) -> OpenBankingConfigStatus:
        config = await self.get_config(db)
        sync_row = await self._get_row(db, _LAST_SYNC_KEY)
        requisitions = await self.list_requisitions(db)
        linked = [req for req in requisitions if is_connection_linked(config, req)]
        configured = self.is_configured(config)
        provider_ready: bool | None = None
        readiness_message: str | None = None
        readiness_status = None
        if configured:
            snapshot = await probe_provider_readiness(config)
            provider_ready = snapshot.provider_ready
            readiness_message = snapshot.readiness_message
            readiness_status = snapshot.readiness_status
        return OpenBankingConfigStatus(
            provider=config.provider,
            application_id=config.application_id,
            private_key_set=bool(config.private_key_pem),
            environment=config.environment,
            secret_id=config.secret_id,
            secret_key_set=bool(config.secret_key),
            redirect_url=config.redirect_url,
            country=config.country,
            scopes=config.scopes,
            webhook_url=config.webhook_url,
            configured=configured,
            provider_ready=provider_ready,
            readiness_message=readiness_message,
            readiness_status=readiness_status,
            linked_banks=[req.institution_name for req in linked],
            connections_count=len(linked),
            last_sync_at=sync_row.value if sync_row else None,
        )

    async def set_config(
        self, db: AsyncSession, config: OpenBankingConfig
    ) -> OpenBankingConfigStatus:
        current = await self.get_config(db)
        if not config.secret_key:
            config.secret_key = current.secret_key
        if not config.private_key_pem:
            config.private_key_pem = current.private_key_pem
        if not config.access_token:
            config.access_token = current.access_token
        if not config.refresh_token:
            config.refresh_token = current.refresh_token
        if not config.access_expires_at:
            config.access_expires_at = current.access_expires_at
        row = await self._get_row(db, _OPEN_BANKING_KEY)
        payload = seal_json(config.model_dump(mode="json"))
        if row is None:
            db.add(AppSettingRow(key=_OPEN_BANKING_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()
        return await self.get_status(db)

    async def list_requisitions(self, db: AsyncSession) -> list[OpenBankingRequisition]:
        row = await self._get_row(db, _REQUISITIONS_KEY)
        if row is None:
            return []
        raw = json.loads(row.value)
        if not isinstance(raw, list):
            return []
        return [OpenBankingRequisition.model_validate(item) for item in raw]

    async def save_requisitions(
        self, db: AsyncSession, requisitions: list[OpenBankingRequisition]
    ) -> None:
        row = await self._get_row(db, _REQUISITIONS_KEY)
        payload = json.dumps([item.model_dump(mode="json") for item in requisitions])
        if row is None:
            db.add(AppSettingRow(key=_REQUISITIONS_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()

    async def upsert_requisition(
        self, db: AsyncSession, requisition: OpenBankingRequisition
    ) -> None:
        requisitions = await self.list_requisitions(db)
        updated = False
        for index, existing in enumerate(requisitions):
            if existing.id == requisition.id or (
                requisition.reference and existing.reference == requisition.reference
            ):
                requisitions[index] = requisition
                updated = True
                break
        if not updated:
            requisitions.append(requisition)
        await self.save_requisitions(db, requisitions)

    async def store_pending_reference(
        self,
        db: AsyncSession,
        *,
        reference: str,
        requisition_id: str,
        institution_id: str,
        institution_name: str,
        provider: str = "enable_banking",
    ) -> None:
        pending = {
            reference: {
                "requisition_id": requisition_id,
                "institution_id": institution_id,
                "institution_name": institution_name,
                "provider": provider,
            }
        }
        row = await self._get_row(db, _PENDING_KEY)
        existing: dict[str, dict[str, str]] = {}
        if row is not None:
            loaded = json.loads(row.value)
            if isinstance(loaded, dict):
                existing = loaded
        existing.update(pending)
        payload = json.dumps(existing)
        if row is None:
            db.add(AppSettingRow(key=_PENDING_KEY, value=payload))
        else:
            row.value = payload
        await db.commit()

    async def pop_pending_reference(
        self, db: AsyncSession, reference: str
    ) -> dict[str, str] | None:
        row = await self._get_row(db, _PENDING_KEY)
        if row is None:
            return None
        loaded = json.loads(row.value)
        if not isinstance(loaded, dict):
            return None
        entry = loaded.pop(reference, None)
        row.value = json.dumps(loaded)
        await db.commit()
        return entry if isinstance(entry, dict) else None

    async def mark_synced(self, db: AsyncSession) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row = await self._get_row(db, _LAST_SYNC_KEY)
        if row is None:
            db.add(AppSettingRow(key=_LAST_SYNC_KEY, value=now))
        else:
            row.value = now
        await db.commit()

    def build_redirect_url(self, config: OpenBankingConfig, reference: str) -> str:
        base = (config.redirect_url or settings.open_banking_redirect_url).rstrip("/")
        if config.provider == "enable_banking":
            # Enable whitelists exact redirect URLs — state is sent in the auth body.
            return base
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}ref={reference}"

    def new_reference(self) -> str:
        return str(uuid.uuid4())


open_banking_settings_service = OpenBankingSettingsService()
