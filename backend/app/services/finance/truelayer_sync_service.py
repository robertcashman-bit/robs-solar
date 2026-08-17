"""Sync personal accounts and transactions from TrueLayer Open Banking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow
from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.truelayer_client import TrueLayerClient, TrueLayerError
from app.integrations.truelayer_provider import TrueLayerProvider
from app.schemas.finance import (
    FinanceAccountSource,
    TrueLayerConfig,
    TrueLayerSyncResult,
)
from app.services.finance.finance_import_service import finance_import_service
from app.services.finance.finance_ledger_service import finance_ledger_service
from app.services.truelayer_settings_service import truelayer_settings_service


class TrueLayerSyncService:
    async def _access_token(self, db: AsyncSession, config: TrueLayerConfig) -> str:
        tokens = await truelayer_settings_service.get_tokens(db)
        refresh = tokens.get("refresh_token", "")
        access = tokens.get("access_token", "")
        if refresh:
            client = TrueLayerClient(config)
            try:
                refreshed = await client.refresh_access_token(refresh)
            except TrueLayerError as exc:
                raise IntegrationNotConfiguredError(str(exc)) from exc
            tokens.update(
                {
                    "access_token": str(refreshed.get("access_token", "")),
                    "refresh_token": str(refreshed.get("refresh_token", refresh)),
                }
            )
            await truelayer_settings_service.set_tokens(db, tokens)
            return tokens["access_token"]
        if access:
            return access
        raise IntegrationNotConfiguredError(
            "Open Banking is not connected. Complete the bank authorisation flow first."
        )

    async def sync(self, db: AsyncSession, config: TrueLayerConfig) -> TrueLayerSyncResult:
        access_token = await self._access_token(db, config)
        provider = TrueLayerProvider(config, access_token=access_token)
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
                source="open_banking",
                actor="import",
                persist=True,
            )
        except Exception:
            await db.rollback()
            raise
        income, spending = await finance_ledger_service.monthly_flow(
            db, days=30, scope="personal", source="open_banking", prefer_current=False
        )
        if income > 0 or spending > 0:
            await truelayer_settings_service.set_monthly_flow(db, income, spending)
        await truelayer_settings_service.mark_synced(db)
        from app.services.finance.finance_liabilities_service import (
            finance_liabilities_service,
        )

        await finance_liabilities_service.ensure_from_accounts(db)
        fc_imported = False
        fc_message = ""
        try:
            from app.services.finance.funding_circle_sync_service import (
                funding_circle_sync_service,
            )

            fc = await funding_circle_sync_service.sync(db)
            fc_imported = fc.imported
            fc_message = fc.message
        except Exception:
            fc_message = "Funding Circle import skipped"
        await _safe_backup(db, trigger="truelayer_sync")
        message = (
            f"Synced {len(records)} Open Banking account(s), "
            f"imported {imported.get('imported', 0)} transaction(s)"
        )
        if fc_message:
            message = f"{message}. {fc_message}"
        return TrueLayerSyncResult(
            accounts_synced=len(records),
            imported=imported.get("imported", 0),
            duplicates=imported.get("duplicate_count", 0),
            rejected=imported.get("rejected_count", 0),
            message=message,
            funding_circle_imported=fc_imported,
            funding_circle_message=fc_message,
        )

    async def _upsert_account(self, db: AsyncSession, item: dict) -> None:
        external_id = str(item.get("external_id") or "")
        row = await db.scalar(
            select(FinanceAccountRow).where(
                FinanceAccountRow.external_id == external_id,
                FinanceAccountRow.source == FinanceAccountSource.OPEN_BANKING.value,
            )
        )
        now = datetime.now(timezone.utc)
        if row is None:
            row = FinanceAccountRow(
                scope=item["scope"],
                account_type=item["account_type"],
                name=item["name"],
                provider=item.get("provider", "Open Banking"),
                balance_gbp=item.get("balance_gbp", 0.0),
                credit_limit_gbp=item.get("credit_limit_gbp"),
                notes=item.get("notes", ""),
                source=FinanceAccountSource.OPEN_BANKING.value,
                external_id=external_id,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        else:
            row.name = item["name"]
            row.balance_gbp = item.get("balance_gbp", 0.0)
            row.account_type = item["account_type"]
            row.notes = item.get("notes", row.notes)
            row.is_active = True
            row.updated_at = now
        if item.get("credit_limit_gbp") is not None:
            row.credit_limit_gbp = item.get("credit_limit_gbp")


async def _safe_backup(db: AsyncSession, *, trigger: str) -> None:
    try:
        from app.services.finance.finance_backup_service import create_backup

        await create_backup(db, trigger=trigger, actor="import")
    except Exception:
        return


truelayer_sync_service = TrueLayerSyncService()
