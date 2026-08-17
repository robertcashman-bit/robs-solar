import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.db.models import AppSettingRow, FinanceAccountRow, FinanceTransactionRow
from app.db.session import SessionLocal
from app.services.finance.finance_backup_service import (
    create_backup,
    dump_finance_payload,
    restore_local_snapshot,
    restore_payload,
    unwrap_blob_payload,
    wrap_blob_payload,
)
from app.services.finance.money import to_pence


@pytest.mark.asyncio
async def test_backup_omits_integration_secrets_and_restore_skips_existing() -> None:
    async with SessionLocal() as db:
        db.add(
            AppSettingRow(
                key="lunchflow",
                value=json.dumps({"api_key": "lf-secret-should-not-leak"}),
            )
        )
        db.add(AppSettingRow(key="lunchflow_last_sync_at", value="2026-08-16T00:00:00Z"))
        now = datetime.now(timezone.utc)
        db.add(
            FinanceAccountRow(
                name="Current",
                account_type="current",
                scope="personal",
                provider="Test",
                balance_gbp=10,
                notes="",
                source="manual",
                created_at=now,
                updated_at=now,
            )
        )
        db.add(
            FinanceTransactionRow(
                posted_on="2026-08-01",
                amount_pence=to_pence(-12.5),
                currency="GBP",
                description="SHOP",
                account_name="Current",
                external_id="tx-1",
                source="manual",
                fingerprint="fp-backup-1",
                scope="personal",
                created_at=now,
                updated_at=now,
            )
        )
        await db.commit()

        payload = await dump_finance_payload(db)
        assert "lunchflow" not in payload["settings"]
        assert payload["settings"]["lunchflow_last_sync_at"] == "2026-08-16T00:00:00Z"
        wrapped = json.loads(wrap_blob_payload(payload))
        assert wrapped["encrypted"] is True
        assert "SHOP" not in json.dumps(wrapped)
        restored_tx = unwrap_blob_payload(wrapped)["tables"]["finance_transactions"][0]
        assert restored_tx["description"] == "SHOP"

        backup = await create_backup(db, trigger="test", actor="user")
        assert backup["location"] == "local"
        snapshot_id = backup["id"]
        existing_count = len(
            (await db.execute(select(FinanceTransactionRow))).scalars().all()
        )
        assert existing_count == 1

        again = await restore_payload(db, payload, actor="user")
        assert again["restored"]["finance_transactions"] == 0

        row = (await db.execute(select(FinanceTransactionRow))).scalars().one()
        await db.delete(row)
        await db.commit()

        restored = await restore_local_snapshot(db, snapshot_id, actor="user")
        assert restored["restored"]["finance_transactions"] == 1
        txs = list((await db.execute(select(FinanceTransactionRow))).scalars().all())
        assert len(txs) == 1
        assert txs[0].description == "SHOP"
        assert txs[0].amount_pence == to_pence(-12.5)
