"""Import QuickFile bank accounts, statement lines, and live P&L / balance sheet."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow
from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.quickfile_client import QuickFileError
from app.integrations.quickfile_provider import QuickFileProvider
from app.schemas.finance import (
    FinanceAccountSource,
    FinanceAccountType,
    FinanceScope,
    QuickFileConfig,
    QuickFileSyncResult,
)
from app.services.finance.finance_import_service import finance_import_service
from app.services.finance.quickfile_reports_service import quickfile_reports_service
from app.services.finance.sync_lookback import (
    QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS,
    quickfile_lookback_days,
    quickfile_lookback_since,
)
from app.services.quickfile_settings_service import (
    is_quickfile_quota_error,
    quickfile_settings_service,
)

logger = logging.getLogger(__name__)


class QuickFileSyncService:
    async def sync_balances(
        self,
        db: AsyncSession,
        config: QuickFileConfig,
        *,
        include_reports: bool = False,
    ) -> QuickFileSyncResult:
        """Update account + debtor balances only — never Bank_Search history.

        Used by dashboard live-refresh so a stale last_sync cannot burn the
        daily QuickFile API quota on a multi-year year-chunked import.
        """
        if await quickfile_settings_service.is_quota_blocked(db):
            status = await quickfile_settings_service.get_status(db)
            return QuickFileSyncResult(
                accounts_synced=0,
                debtors_gbp=0.0,
                message=(
                    "QuickFile API quota exhausted — retry after midnight UTC. "
                    f"Last error: {status.last_error or 'API request limit exceeded'}"
                ),
            )

        provider = QuickFileProvider(config)
        try:
            accounts = await provider.sync_accounts()
            debtors_gbp = await provider.fetch_debtors_gbp()
        except IntegrationNotConfiguredError:
            raise
        except QuickFileError as exc:
            await quickfile_settings_service.record_error(db, str(exc))
            if is_quickfile_quota_error(exc):
                raise
            raise IntegrationNotConfiguredError(str(exc)) from exc
        except Exception as exc:
            await quickfile_settings_service.record_error(db, str(exc))
            raise

        synced = await self._upsert_accounts_and_debtors(
            db, accounts, debtors_gbp
        )
        await quickfile_settings_service.mark_synced(db)

        message = (
            f"Synced balances for {synced} QuickFile account(s); "
            f"debtors control {debtors_gbp:.2f} GBP"
        )
        reports_synced = False
        if include_reports:
            try:
                await quickfile_reports_service.sync_reports(db, config)
                reports_synced = True
                message += "; P&L and balance sheet synced"
            except Exception as exc:
                logger.warning(
                    "QuickFile reports sync failed after balance sync", exc_info=True
                )
                if is_quickfile_quota_error(exc):
                    await quickfile_settings_service.record_error(db, str(exc))

        return QuickFileSyncResult(
            accounts_synced=synced,
            debtors_gbp=debtors_gbp,
            reports_synced=reports_synced,
            imported=0,
            duplicates=0,
            rejected=0,
            message=message,
        )

    async def sync(
        self,
        db: AsyncSession,
        config: QuickFileConfig,
        *,
        include_reports: bool = True,
        backup: bool = True,
        force_full: bool = False,
        incremental_only: bool = False,
    ) -> QuickFileSyncResult:
        """Import balances and (optionally deep) transaction history.

        - Live refresh must call ``sync_balances`` instead.
        - Daily cron passes ``incremental_only=True`` (~90 days, never 3650).
        - Explicit Sync may run a one-year first import when history is empty.
        - ``force_full=True`` is the only path that runs the ~10-year window.
        """
        if await quickfile_settings_service.is_quota_blocked(db) and not force_full:
            status = await quickfile_settings_service.get_status(db)
            return QuickFileSyncResult(
                accounts_synced=0,
                debtors_gbp=0.0,
                message=(
                    "QuickFile API quota exhausted — retry after midnight UTC. "
                    f"Last error: {status.last_error or 'API request limit exceeded'}"
                ),
            )

        if force_full:
            await quickfile_settings_service.clear_full_history_import(db)
            initial = False
            use_force_full = True
        elif incremental_only:
            # Seed markers from existing Neon history so we never accidentally
            # fall into a deep import on the next non-incremental call.
            await quickfile_settings_service.needs_full_history_import(db)
            initial = False
            use_force_full = False
        else:
            initial = await quickfile_settings_service.needs_full_history_import(db)
            use_force_full = False

        since = quickfile_lookback_since(
            first_sync=initial, force_full=use_force_full
        )
        days = quickfile_lookback_days(
            first_sync=initial, force_full=use_force_full
        )
        provider = QuickFileProvider(config)
        try:
            accounts = await provider.sync_accounts()
            debtors_gbp = await provider.fetch_debtors_gbp()
            raw_txs = await provider.sync_transactions(since=since)
        except IntegrationNotConfiguredError:
            raise
        except QuickFileError as exc:
            await quickfile_settings_service.record_error(db, str(exc))
            raise
        except Exception as exc:
            await quickfile_settings_service.record_error(db, str(exc))
            raise

        synced = await self._upsert_accounts_and_debtors(
            db, accounts, debtors_gbp
        )

        imported = await finance_import_service.commit(
            db,
            raw_txs,
            source="quickfile",
            actor="import",
            persist=True,
        )
        if use_force_full:
            await quickfile_settings_service.mark_full_history_imported(
                db, lookback_days=QUICKFILE_FIRST_SYNC_LOOKBACK_DAYS
            )
        elif initial:
            await quickfile_settings_service.mark_full_history_imported(
                db, lookback_days=days
            )
        await quickfile_settings_service.mark_synced(db)

        if use_force_full:
            window = f"{days}-day force-full sync"
        elif initial:
            window = f"{days}-day first sync"
        else:
            window = f"{days}-day incremental"
        message = (
            f"Synced {synced} QuickFile account(s); "
            f"imported {imported.get('imported', 0)} transaction(s) ({window})"
        )
        message += f"; debtors control {debtors_gbp:.2f} GBP"

        reports_synced = False
        if include_reports:
            try:
                await quickfile_reports_service.sync_reports(db, config)
                reports_synced = True
                message += "; P&L and balance sheet synced"
            except Exception as exc:
                logger.warning(
                    "QuickFile reports sync failed after account sync", exc_info=True
                )
                if is_quickfile_quota_error(exc):
                    await quickfile_settings_service.record_error(db, str(exc))

        if backup:
            await _safe_backup(db, trigger="quickfile_sync")
        return QuickFileSyncResult(
            accounts_synced=synced,
            debtors_gbp=debtors_gbp,
            reports_synced=reports_synced,
            imported=imported.get("imported", 0),
            duplicates=imported.get("duplicate_count", 0),
            rejected=imported.get("rejected_count", 0),
            message=message,
        )

    async def _upsert_accounts_and_debtors(
        self,
        db: AsyncSession,
        accounts: list[dict],
        debtors_gbp: float,
    ) -> int:
        synced = 0
        include_ids = await quickfile_settings_service.get_budget_account_ids(db)
        for item in accounts:
            external_id = str(item.get("external_id") or "")
            if include_ids and external_id and external_id not in include_ids:
                item = {**item, "include_in_budget": False}
            else:
                item = {**item, "include_in_budget": True}
            await self._upsert_account(db, item)
            synced += 1

        await self._upsert_account(
            db,
            {
                "scope": FinanceScope.BUSINESS.value,
                "account_type": FinanceAccountType.DEBTORS.value,
                "name": "Debtors control account",
                "provider": "QuickFile",
                "balance_gbp": debtors_gbp,
                "external_id": "quickfile-debtors",
                "notes": "Debtors control balance from QuickFile balance sheet",
            },
        )
        return synced + 1

    async def _upsert_account(self, db: AsyncSession, item: dict) -> None:
        external_id = str(item.get("external_id") or "")
        row = await db.scalar(
            select(FinanceAccountRow).where(
                FinanceAccountRow.external_id == external_id,
                FinanceAccountRow.source == FinanceAccountSource.QUICKFILE.value,
            )
        )
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        if row is None:
            row = FinanceAccountRow(
                scope=item["scope"],
                account_type=item["account_type"],
                name=item["name"],
                provider=item.get("provider", "QuickFile"),
                balance_gbp=item.get("balance_gbp", 0.0),
                notes=item.get("notes", ""),
                source=FinanceAccountSource.QUICKFILE.value,
                external_id=external_id,
                is_active=bool(item.get("include_in_budget", True)),
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        else:
            row.name = item["name"]
            row.balance_gbp = item.get("balance_gbp", 0.0)
            row.account_type = item["account_type"]
            row.notes = item.get("notes", row.notes)
            row.is_active = bool(item.get("include_in_budget", True))
            row.updated_at = now
        await db.commit()


async def _safe_backup(db: AsyncSession, *, trigger: str) -> None:
    try:
        from app.services.finance.finance_backup_service import create_backup

        await create_backup(db, trigger=trigger, actor="import")
    except Exception:
        logger.warning("QuickFile post-sync backup failed", exc_info=True)


quickfile_sync_service = QuickFileSyncService()
