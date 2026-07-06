"""GoCardless Open Banking adapter (legacy)."""

from __future__ import annotations

from typing import Any

from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.gocardless_client import GoCardlessClient, GoCardlessError
from app.schemas.finance import OpenBankingConfig, OpenBankingRequisition


class GoCardlessOpenBankingAdapter:
    provider = "gocardless"

    def __init__(self, config: OpenBankingConfig) -> None:
        self._config = config
        self._client = GoCardlessClient(config)

    @property
    def client(self) -> GoCardlessClient:
        return self._client

    def _ensure_configured(self) -> None:
        if not (self._config.secret_id and self._config.secret_key):
            raise IntegrationNotConfiguredError(
                "GoCardless Open Banking is not configured. Add secret ID and secret key "
                "under Settings → Finance → Open Banking (legacy)."
            )

    async def test_connection(self) -> dict[str, object]:
        self._ensure_configured()
        try:
            return await self._client.test_connection()
        except GoCardlessError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc

    async def list_institutions(
        self, *, country: str = "gb", query: str = ""
    ) -> list[dict[str, str]]:
        self._ensure_configured()
        try:
            institutions = await self._client.list_institutions(country=country)
        except GoCardlessError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
        needle = query.strip().lower()
        results: list[dict[str, str]] = []
        for item in institutions:
            institution_id = str(item.get("id") or "")
            name = str(item.get("name") or institution_id)
            if not institution_id:
                continue
            if needle and needle not in name.lower() and needle not in institution_id.lower():
                continue
            results.append(
                {
                    "id": institution_id,
                    "name": name,
                    "logo": str(item.get("logo") or ""),
                }
            )
        results.sort(key=lambda row: row["name"].lower())
        return results[:40]

    async def create_connection(
        self,
        *,
        institution_id: str,
        institution_name: str,
        redirect_url: str,
        reference: str,
    ) -> dict[str, str]:
        self._ensure_configured()
        try:
            body = await self._client.create_requisition(
                institution_id=institution_id,
                redirect_url=redirect_url,
                reference=reference,
            )
        except GoCardlessError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
        requisition_id = str(body.get("id") or "")
        link = str(body.get("link") or "")
        if not requisition_id or not link:
            raise IntegrationNotConfiguredError(
                "GoCardless did not return a bank authorisation link"
            )
        return {
            "requisition_id": requisition_id,
            "link": link,
            "institution_id": institution_id,
            "institution_name": institution_name,
            "reference": reference,
        }

    async def finalize_connection(
        self,
        connection: OpenBankingRequisition,
        *,
        code: str | None = None,
    ) -> OpenBankingRequisition:
        self._ensure_configured()
        try:
            body = await self._client.get_requisition(connection.id)
        except GoCardlessError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
        connection.status = str(body.get("status") or connection.status)
        accounts = body.get("accounts")
        if isinstance(accounts, list):
            connection.account_ids = [str(item) for item in accounts if item]
        connection.provider = self.provider
        return connection

    async def sync_accounts_for_connections(
        self,
        connections: list[OpenBankingRequisition],
    ) -> list[dict[str, Any]]:
        self._ensure_configured()
        records: list[dict[str, Any]] = []
        for connection in connections:
            if not self.is_linked(connection):
                continue
            for account_id in connection.account_ids:
                record = await self._client.fetch_account_record(
                    account_id=account_id,
                    institution_name=connection.institution_name,
                )
                if record is not None:
                    records.append(record)
        return records

    def export_tokens(self) -> dict[str, str | None]:
        return self._client.export_tokens()

    def is_linked(self, connection: OpenBankingRequisition) -> bool:
        return connection.status == "LN" and bool(connection.account_ids)
