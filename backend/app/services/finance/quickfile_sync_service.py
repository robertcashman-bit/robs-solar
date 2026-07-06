"""Import QuickFile bank accounts into finance tables."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow
from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.quickfile_provider import QuickFileProvider
from app.schemas.finance import (
    FinanceAccountSource,
    FinanceAccountType,
    FinanceScope,
    QuickFileConfig,
    QuickFileSyncResult,
)
from app.services.finance.quickfile_reports_service import quickfile_reports_service
from app.services.quickfile_settings_service import quickfile_settings_service


class QuickFileSyncService:
    async def sync(self, db: AsyncSession, config: QuickFileConfig) -> QuickFileSyncResult:
        provider = QuickFileProvider(config)
        try:
            accounts = await provider.sync_accounts()
            debtors_gbp = await provider.fetch_debtors_gbp()
        except IntegrationNotConfiguredError as exc:
            raise exc

        synced = 0
        for item in accounts:
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
        synced += 1

        await quickfile_settings_service.mark_synced(db)
        message = f"Synced {synced} QuickFile account(s)"
        message += f"; debtors control {debtors_gbp:.2f} GBP"

        reports_synced = False
        try:
            await quickfile_reports_service.sync_reports(db, config)
            reports_synced = True
            message += "; P&L and balance sheet synced"
        except Exception:
            pass

        return QuickFileSyncResult(
            accounts_synced=synced,
            debtors_gbp=debtors_gbp,
            reports_synced=reports_synced,
            message=message,
        )

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
        await db.commit()


quickfile_sync_service = QuickFileSyncService()
