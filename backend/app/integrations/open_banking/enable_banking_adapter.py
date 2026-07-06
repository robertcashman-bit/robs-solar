"""Enable Banking Open Banking adapter."""

from __future__ import annotations

from typing import Any

from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.enable_banking_client import (
    EnableBankingClient,
    EnableBankingError,
    parse_institution_id,
)
from app.schemas.finance import OpenBankingConfig, OpenBankingRequisition


class EnableBankingAdapter:
    provider = "enable_banking"

    def __init__(self, config: OpenBankingConfig) -> None:
        self._config = config
        self._client = EnableBankingClient(config)

    def _ensure_configured(self) -> None:
        if not (self._config.application_id and self._config.private_key_pem):
            raise IntegrationNotConfiguredError(
                "Enable Banking is not configured. Add Application ID and private key "
                "under Settings → Finance → Open Banking."
            )

    async def test_connection(self) -> dict[str, object]:
        self._ensure_configured()
        try:
            return await self._client.test_connection()
        except EnableBankingError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc

    async def list_institutions(
        self, *, country: str = "gb", query: str = ""
    ) -> list[dict[str, str]]:
        self._ensure_configured()
        try:
            rows = await self._client.list_aspsps(country=country.upper(), query=query)
        except EnableBankingError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
        return [
            {"id": str(row["id"]), "name": str(row["name"]), "logo": str(row.get("logo") or "")}
            for row in rows
        ]

    async def create_connection(
        self,
        *,
        institution_id: str,
        institution_name: str,
        redirect_url: str,
        reference: str,
    ) -> dict[str, str]:
        self._ensure_configured()
        country, aspsp_name = parse_institution_id(institution_id)
        if not aspsp_name:
            aspsp_name = institution_name
        try:
            body = await self._client.start_auth(
                country=country,
                aspsp_name=aspsp_name,
                redirect_url=redirect_url,
                state=reference,
            )
        except EnableBankingError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
        link = str(body.get("url") or "")
        authorization_id = str(body.get("authorization_id") or reference)
        if not link:
            raise IntegrationNotConfiguredError(
                "Enable Banking did not return a bank authorisation link"
            )
        return {
            "requisition_id": authorization_id,
            "link": link,
            "institution_id": institution_id,
            "institution_name": institution_name,
            "reference": reference,
            "state": reference,
        }

    async def finalize_connection(
        self,
        connection: OpenBankingRequisition,
        *,
        code: str | None = None,
    ) -> OpenBankingRequisition:
        self._ensure_configured()
        if not code:
            raise IntegrationNotConfiguredError(
                "Enable Banking finalisation requires an authorisation code from the bank callback"
            )
        try:
            body = await self._client.authorize_session(code=code)
        except EnableBankingError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc
        connection.id = str(body.get("session_id") or connection.id)
        connection.status = "AUTHORIZED"
        accounts = body.get("accounts")
        account_ids: list[str] = []
        if isinstance(accounts, list):
            for account in accounts:
                if isinstance(account, dict) and account.get("uid"):
                    account_ids.append(str(account["uid"]))
        connection.account_ids = account_ids
        connection.provider = self.provider
        return connection

    async def sync_accounts_for_connections(
        self,
        connections: list[OpenBankingRequisition],
    ) -> list[dict[str, Any]]:
        self._ensure_configured()
        records: list[dict[str, Any]] = []
        for connection in connections:
            if not self.is_linked(connection) or not connection.account_ids:
                continue
            session_body: dict[str, Any] | None = None
            try:
                session_body = await self._client.get_session(connection.id)
            except EnableBankingError:
                session_body = None
            accounts_by_uid: dict[str, dict[str, Any]] = {}
            if session_body:
                accounts = session_body.get("accounts")
                if isinstance(accounts, list):
                    for account in accounts:
                        if isinstance(account, dict) and account.get("uid"):
                            accounts_by_uid[str(account["uid"])] = account
            for account_id in connection.account_ids:
                account = accounts_by_uid.get(account_id, {"uid": account_id})
                record = await self._client.fetch_account_record(
                    account=account,
                    institution_name=connection.institution_name,
                )
                if record is not None:
                    records.append(record)
        return records

    def export_tokens(self) -> dict[str, str | None]:
        return {}

    def is_linked(self, connection: OpenBankingRequisition) -> bool:
        return connection.status == "AUTHORIZED" and bool(connection.account_ids)
