"""Sync personal accounts and transactions from Lunch Flow Open Banking."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow
from app.integrations.lunchflow_provider import LunchFlowProvider
from app.schemas.finance import FinanceAccountSource, LunchFlowConfig, LunchFlowSyncResult
from app.services.finance.finance_accounts_service import (
    _prefer_lunchflow_account,
    finance_accounts_service,
)
from app.services.finance.finance_import_service import finance_import_service
from app.services.finance.finance_ledger_service import finance_ledger_service
from app.services.finance.lunchflow_account_ids import (
    LUNCHFLOW_SOURCES,
    lunchflow_external_id_aliases,
    normalize_lunchflow_external_id,
)
from app.services.finance.lunchflow_scope import (
    mark_quickfile_shadow_if_needed,
    parse_quickfile_shadow_map,
    sync_balance_gbp,
)
from app.services.finance.sync_lookback import lookback_since
from app.services.lunchflow_settings_service import lunchflow_settings_service


class LunchFlowSyncService:
    async def sync_balances(
        self, db: AsyncSession, config: LunchFlowConfig
    ) -> LunchFlowSyncResult:
        """Update account balances only — no year-long transaction import."""
        provider = LunchFlowProvider(config)
        records = await provider.sync_accounts()
        shadow_map = parse_quickfile_shadow_map(config.quickfile_shadow_map)
        try:
            for item in records:
                await self._upsert_account(db, item, quickfile_shadow_map=shadow_map)
            await finance_accounts_service.dedupe_active_lunchflow_accounts(db)
            await db.flush()
        except Exception:
            await db.rollback()
            raise
        await lunchflow_settings_service.mark_synced(db)
        return LunchFlowSyncResult(
            accounts_synced=len(records),
            imported=0,
            duplicates=0,
            rejected=0,
            message=f"Synced balances for {len(records)} Lunch Flow account(s)",
        )

    async def sync(self, db: AsyncSession, config: LunchFlowConfig) -> LunchFlowSyncResult:
        provider = LunchFlowProvider(config)
        records = await provider.sync_accounts()
        shadow_map = parse_quickfile_shadow_map(config.quickfile_shadow_map)
        first_sync = await lunchflow_settings_service.needs_full_history_import(db)
        since = lookback_since(first_sync=first_sync)
        try:
            for item in records:
                await self._upsert_account(db, item, quickfile_shadow_map=shadow_map)
            await finance_accounts_service.dedupe_active_lunchflow_accounts(db)
            await db.flush()
            # First successful full import pulls ~730 days. Later syncs stay
            # incremental (~90 days); fingerprints dedupe.
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
        if first_sync:
            await lunchflow_settings_service.mark_full_history_imported(db)
        await lunchflow_settings_service.mark_synced(db)
        try:
            from app.services.finance.funding_circle_sync_service import (
                funding_circle_sync_service,
            )

            await funding_circle_sync_service.sync(db)
        except Exception:
            pass
        await _safe_backup(db, trigger="lunchflow_sync")
        window = "730-day first sync" if first_sync else "90-day incremental"
        return LunchFlowSyncResult(
            accounts_synced=len(records),
            imported=imported.get("imported", 0),
            duplicates=imported.get("duplicate_count", 0),
            rejected=imported.get("rejected_count", 0),
            message=(
                f"Synced {len(records)} Lunch Flow account(s), "
                f"imported {imported.get('imported', 0)} transaction(s) "
                f"({window})"
            ),
        )

    async def _upsert_account(
        self,
        db: AsyncSession,
        item: dict,
        *,
        quickfile_shadow_map: dict[str, int] | None = None,
    ) -> None:
        external_id = str(item.get("external_id") or "")
        canonical = normalize_lunchflow_external_id(external_id)
        if not canonical:
            return

        # Match bare id and legacy ``lunchflow:id`` / ``lunch_flow:id`` forms.
        aliases = lunchflow_external_id_aliases(canonical)
        matches = list(
            (
                await db.scalars(
                    select(FinanceAccountRow).where(
                        FinanceAccountRow.source.in_(tuple(LUNCHFLOW_SOURCES)),
                        FinanceAccountRow.external_id.in_(tuple(aliases)),
                    )
                )
            ).all()
        )

        now = datetime.now(timezone.utc)
        balance = sync_balance_gbp(
            account_type=str(item["account_type"]),
            credit_limit_gbp=item.get("credit_limit_gbp"),
            item=item,
        )
        if not matches:
            row = FinanceAccountRow(
                scope=item["scope"],
                account_type=item["account_type"],
                name=item["name"],
                provider=item.get("provider", "Lunch Flow"),
                balance_gbp=balance,
                credit_limit_gbp=item.get("credit_limit_gbp"),
                notes=item.get("notes", ""),
                source=FinanceAccountSource.LUNCHFLOW.value,
                external_id=canonical,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            await db.flush()
            await mark_quickfile_shadow_if_needed(
                db, row, quickfile_shadow_map=quickfile_shadow_map
            )
            return

        # Prefer an already-active row when choosing which duplicate to update.
        active = [row for row in matches if row.is_active]
        pool = active or matches
        keeper = pool[0]
        for candidate in pool[1:]:
            keeper = _prefer_lunchflow_account(keeper, candidate)

        if item.get("credit_limit_gbp") is not None:
            keeper.credit_limit_gbp = item.get("credit_limit_gbp")
        keeper.balance_gbp = sync_balance_gbp(
            account_type=str(keeper.account_type),
            credit_limit_gbp=keeper.credit_limit_gbp,
            item=item,
        )
        keeper.provider = item.get("provider", keeper.provider)
        keeper.source = FinanceAccountSource.LUNCHFLOW.value
        keeper.external_id = canonical
        keeper.updated_at = now
        await mark_quickfile_shadow_if_needed(
            db, keeper, quickfile_shadow_map=quickfile_shadow_map
        )
        # Extra alias rows stay until dedupe_active_lunchflow_accounts archives them
        # and re-points any liabilities that still link to those ids.

async def _safe_backup(db: AsyncSession, *, trigger: str) -> None:
    try:
        from app.services.finance.finance_backup_service import create_backup

        await create_backup(db, trigger=trigger, actor="import")
    except Exception:
        return


lunchflow_sync_service = LunchFlowSyncService()
