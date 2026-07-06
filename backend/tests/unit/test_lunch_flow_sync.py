"""Unit tests for Lunch Flow sync service."""

from __future__ import annotations

import httpx
import pytest
import respx
from sqlalchemy import delete, select

from app.db.models import FinanceAccountRow, FinanceTransactionRow
from app.db.session import SessionLocal
from app.schemas.finance import FinanceAccountSource, LunchFlowConfig
from app.services.finance.lunch_flow_sync_service import lunch_flow_sync_service


@pytest.mark.asyncio
@respx.mock
async def test_sync_imports_accounts_and_transactions() -> None:
    respx.get("https://www.lunchflow.app/api/v1/accounts").mock(
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
    respx.get("https://www.lunchflow.app/api/v1/accounts/11/balance").mock(
        return_value=httpx.Response(
            200,
            json={"balance": {"amount": 350.0, "currency": "GBP"}},
        )
    )
    respx.get("https://www.lunchflow.app/api/v1/accounts/11/transactions").mock(
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
        await db.execute(delete(FinanceTransactionRow))
        await db.execute(delete(FinanceAccountRow))
        await db.commit()

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


@pytest.mark.asyncio
@respx.mock
async def test_sync_retires_disconnected_accounts_and_skips_non_gbp() -> None:
    respx.get("https://www.lunchflow.app/api/v1/accounts").mock(
        return_value=httpx.Response(
            200,
            json={
                "accounts": [
                    {
                        "id": 21,
                        "name": "Old Lloyds current",
                        "institution_name": "Lloyds Bank",
                        "institution_logo": "",
                        "provider": "gocardless",
                        "status": "DISCONNECTED",
                    },
                    {
                        "id": 22,
                        "name": "Euro account",
                        "institution_name": "Virgin Money",
                        "institution_logo": "",
                        "provider": "gocardless",
                        "currency": "EUR",
                        "status": "ACTIVE",
                    },
                ],
                "total": 2,
            },
        )
    )

    from datetime import datetime, timezone

    async with SessionLocal() as db:
        await db.execute(delete(FinanceTransactionRow))
        await db.execute(delete(FinanceAccountRow))
        await db.commit()

        now = datetime.now(timezone.utc)
        db.add(
            FinanceAccountRow(
                scope="personal",
                account_type="current",
                name="Old Lloyds current",
                provider="Lloyds Bank",
                balance_gbp=900.0,
                source=FinanceAccountSource.LUNCH_FLOW.value,
                external_id="lunchflow:21",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        await db.commit()

        result = await lunch_flow_sync_service.sync(db, LunchFlowConfig(api_key="secret"))
        assert result.accounts_synced == 0
        assert "disconnected" in result.message
        assert "non-GBP" in result.message

        stale = await db.scalar(
            select(FinanceAccountRow).where(FinanceAccountRow.external_id == "lunchflow:21")
        )
        assert stale is not None
        assert stale.is_active is False

        euro = await db.scalar(
            select(FinanceAccountRow).where(FinanceAccountRow.external_id == "lunchflow:22")
        )
        assert euro is None
