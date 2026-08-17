"""Sync personal accounts and transactions from Lunch Flow Open Banking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow
from app.integrations.lunchflow_provider import LunchFlowProvider
from app.schemas.finance import FinanceAccountSource, LunchFlowConfig, LunchFlowSyncResult
from app.services.finance.finance_import_service import finance_import_service
from app.services.finance.finance_ledger_service import finance_ledger_service
from app.services.lunchflow_settings_service import lunchflow_settings_service


class LunchFlowSyncService:
    async def sync(self, db: AsyncSession, config: LunchFlowConfig) -> LunchFlowSyncResult:
        provider = LunchFlowProvider(config)
        records = await provider.sync_accounts()
        try:
            for item in records:
                await self._upsert_account(db, item)
            await db.flush()
            since = (datetime.now(timezone.utc) - timedelta(days=365)).date().isoformat()
            raw_txs = await provider.sync_transactions(since=since)
            imported = await finance_import_service.commit(
                db,
                raw_txs,
                source="lunchflow",
                actor="import",
                persist=True,
            )
        except Exception:
            await db.rollback()
            raise
        income, spending = await finance_ledger_service.monthly_flow(
            db, days=30, scope="personal", source="lunchflow"
        )
        if income > 0 or spending > 0:
            await lunchflow_settings_service.set_monthly_flow(db, income, spending)
        await lunchflow_settings_service.mark_synced(db)
        await _safe_backup(db, trigger="lunchflow_sync")
        return LunchFlowSyncResult(
            accounts_synced=len(records),
            imported=imported.get("imported", 0),
            duplicates=imported.get("duplicate_count", 0),
            rejected=imported.get("rejected_count", 0),
            message=(
                f"Synced {len(records)} Lunch Flow account(s), "
                f"imported {imported.get('imported', 0)} transaction(s)"
            ),
        )

    async def _upsert_account(self, db: AsyncSession, item: dict) -> None:
        external_id = str(item.get("external_id") or "")
        row = await db.scalar(
            select(FinanceAccountRow).where(
                FinanceAccountRow.external_id == external_id,
                FinanceAccountRow.source.in_(
                    (FinanceAccountSource.LUNCHFLOW.value, "lunch_flow")
                ),
            )
        )
        now = datetime.now(timezone.utc)
        if row is None:
            row = FinanceAccountRow(
                scope=item["scope"],
                account_type=item["account_type"],
                name=item["name"],
                provider=item.get("provider", "Lunch Flow"),
                balance_gbp=item.get("balance_gbp", 0.0),
                credit_limit_gbp=item.get("credit_limit_gbp"),
                notes=item.get("notes", ""),
                source=FinanceAccountSource.LUNCHFLOW.value,
                external_id=external_id,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        else:
            row.name = item["name"]
            row.balance_gbp = item.get("balance_gbp", 0.0)
            if item.get("credit_limit_gbp") is not None:
                row.credit_limit_gbp = item.get("credit_limit_gbp")
            row.account_type = item["account_type"]
            row.provider = item.get("provider", row.provider)
            row.notes = item.get("notes", row.notes)
            row.source = FinanceAccountSource.LUNCHFLOW.value
            row.is_active = True
            row.updated_at = now


async def _safe_backup(db: AsyncSession, *, trigger: str) -> None:
    try:
        from app.services.finance.finance_backup_service import create_backup

        await create_backup(db, trigger=trigger, actor="import")
    except Exception:
        return


lunchflow_sync_service = LunchFlowSyncService()
