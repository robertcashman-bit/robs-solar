"""Open Banking adapter protocol."""

from __future__ import annotations

from typing import Any, Protocol

from app.schemas.finance import OpenBankingRequisition


class OpenBankingAdapter(Protocol):
    provider: str

    async def test_connection(self) -> dict[str, object]: ...

    async def list_institutions(
        self, *, country: str = "gb", query: str = ""
    ) -> list[dict[str, str]]: ...

    async def create_connection(
        self,
        *,
        institution_id: str,
        institution_name: str,
        redirect_url: str,
        reference: str,
    ) -> dict[str, str]: ...

    async def finalize_connection(
        self,
        connection: OpenBankingRequisition,
        *,
        code: str | None = None,
    ) -> OpenBankingRequisition: ...

    async def sync_accounts_for_connections(
        self,
        connections: list[OpenBankingRequisition],
    ) -> list[dict[str, Any]]: ...

    def export_tokens(self) -> dict[str, str | None]: ...

    def is_linked(self, connection: OpenBankingRequisition) -> bool: ...
