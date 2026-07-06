"""Unit tests for simplified bank connections service."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.db.models import FinanceAccountRow, FinanceTransactionRow
from app.db.session import SessionLocal
from app.schemas.finance import (
    BankConnectionMethod,
    BankConnectionStatus,
    FinanceAccountSource,
    OpenBankingConfig,
    OpenBankingRequisition,
)
from app.services.finance.bank_connections_service import (
    TARGET_BANKS,
    disconnect,
    get_connections,
)
from app.services.lunch_flow_settings_service import lunch_flow_settings_service
from app.services.open_banking_settings_service import open_banking_settings_service
from tests.unit.test_enable_banking_client import _test_private_key_pem


async def _clear_lunch_flow_settings(db) -> None:
    row = await lunch_flow_settings_service._get_row(db, "lunch_flow")
    if row is not None:
        await db.delete(row)
        await db.commit()


@pytest.mark.asyncio
async def test_get_connections_returns_all_target_banks() -> None:
    async with SessionLocal() as db:
        connections = await get_connections(db)
    assert len(connections) == len(TARGET_BANKS)
    ids = {item.id for item in connections}
    assert ids == set(TARGET_BANKS.keys())


@pytest.mark.asyncio
async def test_get_connections_open_banking_not_configured_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "enable_banking_application_id", "")
    monkeypatch.setattr(settings, "enable_banking_private_key_pem", "")
    monkeypatch.setattr(settings, "enable_banking_private_key_path", "")
    monkeypatch.setattr(settings, "open_banking_secret_id", "")
    monkeypatch.setattr(settings, "open_banking_secret_key", "")
    monkeypatch.setattr(settings, "lunch_flow_api_key", "")

    async with SessionLocal() as db:
        row = await open_banking_settings_service._get_row(db, "open_banking")
        if row is not None:
            await db.delete(row)
            await db.commit()
        await _clear_lunch_flow_settings(db)
        connections = await get_connections(db)
    lloyds = next(item for item in connections if item.id == "lloyds")
    assert lloyds.method == BankConnectionMethod.OPEN_BANKING
    assert lloyds.status == BankConnectionStatus.NOT_CONFIGURED
    assert "Open Banking is not set up yet" in lloyds.status_message


@pytest.mark.asyncio
async def test_get_connections_linked_lloyds_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "lunch_flow_api_key", "")

    async with SessionLocal() as db:
        await db.execute(delete(FinanceAccountRow))
        await db.commit()
        await _clear_lunch_flow_settings(db)
        await open_banking_settings_service.set_config(
            db,
            OpenBankingConfig(
                application_id="app-123",
                private_key_pem=_test_private_key_pem(),
            ),
        )
        await open_banking_settings_service.save_requisitions(
            db,
            [
                OpenBankingRequisition(
                    id="sess-1",
                    institution_id="GB:Lloyds Bank",
                    institution_name="Lloyds Bank",
                    status="AUTHORIZED",
                    account_ids=["acc-1"],
                )
            ],
        )
        now = datetime.now(timezone.utc)
        db.add(
            FinanceAccountRow(
                scope="personal",
                account_type="current",
                name="Lloyds current",
                provider="Lloyds Bank",
                balance_gbp=1200.0,
                source=FinanceAccountSource.OPEN_BANKING.value,
                external_id="openbanking:enable:acc-1",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        await db.commit()
        connections = await get_connections(db)

    lloyds = next(item for item in connections if item.id == "lloyds")
    assert lloyds.status == BankConnectionStatus.CONNECTED
    assert lloyds.account_count == 1
    assert lloyds.balance_gbp == 1200.0
    assert "Connected" in lloyds.status_message


@pytest.mark.asyncio
async def test_disconnect_removes_open_banking_requisition() -> None:
    async with SessionLocal() as db:
        await open_banking_settings_service.save_requisitions(
            db,
            [
                OpenBankingRequisition(
                    id="sess-mbna",
                    institution_id="GB:MBNA",
                    institution_name="MBNA",
                    status="AUTHORIZED",
                    account_ids=["acc-mbna"],
                ),
                OpenBankingRequisition(
                    id="sess-virgin",
                    institution_id="GB:Virgin Money",
                    institution_name="Virgin Money",
                    status="AUTHORIZED",
                    account_ids=["acc-virgin"],
                ),
            ],
        )
        now = datetime.now(timezone.utc)
        db.add(
            FinanceAccountRow(
                scope="personal",
                account_type="credit_card",
                name="MBNA card",
                provider="MBNA",
                balance_gbp=250.0,
                source=FinanceAccountSource.OPEN_BANKING.value,
                external_id="openbanking:enable:acc-mbna",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        await db.commit()

        assert await disconnect(db, "mbna") is True
        remaining = await open_banking_settings_service.list_requisitions(db)
        assert len(remaining) == 1
        assert remaining[0].institution_name == "Virgin Money"

        account = await db.scalar(
            select(FinanceAccountRow).where(
                FinanceAccountRow.external_id == "openbanking:enable:acc-mbna"
            )
        )
        assert account is not None
        assert account.is_active is False


@pytest.mark.asyncio
async def test_disconnect_rejects_non_open_banking_bank() -> None:
    async with SessionLocal() as db:
        assert await disconnect(db, "capital_on_tap") is False
        assert await disconnect(db, "funding_circle") is False
        assert await disconnect(db, "missing") is False
