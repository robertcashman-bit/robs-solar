"""Open Banking provider facade."""

from __future__ import annotations

from typing import Any

from app.integrations.open_banking.factory import get_open_banking_adapter
from app.integrations.open_banking.gocardless_adapter import GoCardlessOpenBankingAdapter
from app.schemas.finance import OpenBankingConfig, OpenBankingRequisition


class OpenBankingProvider:
    name = "open_banking"

    def __init__(self, config: OpenBankingConfig) -> None:
        self._config = config
        self._adapter = get_open_banking_adapter(config)

    @property
    def adapter(self):
        return self._adapter

    @property
    def client(self):
        if isinstance(self._adapter, GoCardlessOpenBankingAdapter):
            return self._adapter.client
        return self._adapter

    async def test_connection(self) -> dict[str, object]:
        return await self._adapter.test_connection()

    async def list_institutions(
        self, *, country: str = "gb", query: str = ""
    ) -> list[dict[str, str]]:
        return await self._adapter.list_institutions(country=country, query=query)

    async def create_connection(
        self,
        *,
        institution_id: str,
        institution_name: str,
        redirect_url: str,
        reference: str,
    ) -> dict[str, str]:
        return await self._adapter.create_connection(
            institution_id=institution_id,
            institution_name=institution_name,
            redirect_url=redirect_url,
            reference=reference,
        )

    async def finalize_requisition(
        self,
        requisition: OpenBankingRequisition,
        *,
        code: str | None = None,
    ) -> OpenBankingRequisition:
        return await self._adapter.finalize_connection(requisition, code=code)

    async def sync_accounts(
        self,
        requisitions: list | None = None,
    ) -> list[dict[str, Any]]:
        if requisitions is None:
            from app.integrations.base import IntegrationNotConfiguredError

            raise IntegrationNotConfiguredError(
                "Open Banking sync requires stored bank connections."
            )
        return await self.sync_accounts_for_requisitions(requisitions)

    async def sync_accounts_for_requisitions(
        self,
        requisitions: list[OpenBankingRequisition],
    ) -> list[dict[str, Any]]:
        return await self._adapter.sync_accounts_for_connections(requisitions)

    def is_linked(self, requisition: OpenBankingRequisition) -> bool:
        return self._adapter.is_linked(requisition)

    async def sync_transactions(self, *, since: str | None = None) -> list[dict[str, Any]]:
        from app.integrations.base import IntegrationNotConfiguredError

        raise IntegrationNotConfiguredError(
            "Open Banking transaction sync is not enabled yet. Balances sync is available."
        )
