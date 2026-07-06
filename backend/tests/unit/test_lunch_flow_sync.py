"""Unit tests for Lunch Flow sync service."""

from __future__ import annotations

import httpx
import pytest
import respx
from sqlalchemy import select

from app.db.models import FinanceAccountRow, FinanceTransactionRow
from app.db.session import SessionLocal
from app.schemas.finance import FinanceAccountSource, LunchFlowConfig
from app.services.finance.lunch_flow_sync_service import lunch_flow_sync_service


@pytest.mark.asyncio
@respx.mock
async def test_sync_imports_accounts_and_transactions() -> None:
    respx.get("https://lunchflow.app/api/v1/accounts").mock(
        return_value=httpx.Response(
            200,
            json={
                "accounts": [
                    {
                        "id": 11,
                        "name": "MBNA card",
                        "institution_name": "MBNA",
                        "institution_logo": "",
                        "provider": "gocardless",
                        "status": "ACTIVE",
                    }
                ]
            },
        )
    )
    # Official spec shape: balance.amount, merchant, isPending, nullable id.
    respx.get("https://lunchflow.app/api/v1/accounts/11/balance").mock(
        return_value=httpx.Response(
            200,
            json={"balance": {"amount": 350.0, "currency": "GBP"}},
        )
    )
    respx.get("https://lunchflow.app/api/v1/accounts/11/transactions").mock(
        return_value=httpx.Response(
            200,
            json={
                "transactions": [
                    {
                        "id": "abc",
                        "accountId": 11,
                        "date": "2026-07-02",
                        "amount": -15.0,
                        "currency": "GBP",
                        "description": "Groceries",
                        "merchant": "Tesco",
                        "isPending": False,
                    },
                    {
                        "id": None,
                        "accountId": 11,
                        "date": "2026-07-03",
                        "amount": -9.5,
                        "currency": "GBP",
                        "description": "Pending card payment",
                        "isPending": True,
                    },
                ]
            },
        )
    )

    async with SessionLocal() as db:
        result = await lunch_flow_sync_service.sync(db, LunchFlowConfig(api_key="secret"))
        assert result.accounts_synced == 1
        assert result.transactions_synced == 2

        account = await db.scalar(
            select(FinanceAccountRow).where(FinanceAccountRow.external_id == "lunchflow:11")
        )
        assert account is not None
        assert account.source == FinanceAccountSource.LUNCH_FLOW.value
        assert account.balance_gbp == 350.0

        tx = await db.scalar(
            select(FinanceTransactionRow).where(
                FinanceTransactionRow.external_id == "lunchflow:11:abc"
            )
        )
        assert tx is not None
        assert tx.amount_gbp == -15.0
        assert tx.merchant == "Tesco"
        assert tx.is_pending is False

        pending_rows = await db.scalars(
            select(FinanceTransactionRow).where(FinanceTransactionRow.is_pending.is_(True))
        )
        pending = pending_rows.all()
        assert len(pending) == 1
        # Null transaction id must not produce a bare "lunchflow:11:" external id.
        assert pending[0].external_id != "lunchflow:11:"
