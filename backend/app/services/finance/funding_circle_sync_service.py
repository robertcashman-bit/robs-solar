"""Import the Funding Circle loan from imported bank-feed transactions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow, FinanceLiabilityRow, FinanceTransactionRow
from app.schemas.finance import (
    DebtType,
    FinanceAccountSource,
    FinanceAccountType,
    FinanceScope,
    FundingCircleSyncResult,
)
from app.services.finance.funding_circle import (
    is_funding_circle_text,
    next_outstanding,
    summarise_activity,
)
from app.services.funding_circle_settings_service import funding_circle_settings_service

LOAN_NAME = "Funding Circle"
_EXTERNAL_ID = "funding-circle"


class FundingCircleSyncService:
    async def sync(
        self,
        db: AsyncSession,
        *,
        transactions: list[dict] | None = None,
    ) -> FundingCircleSyncResult:
        config = await funding_circle_settings_service.get_config(db)
        existing = await self._existing_liability(db)
        if existing is not None and (existing.balance_gbp or 0) > 0:
            current = existing.balance_gbp
        elif config.outstanding_gbp is not None:
            current = config.outstanding_gbp
        else:
            current = None
        first_sync = not config.last_txn_on

        if transactions is None:
            transactions = await self._load_bank_transactions(db)

        activity = summarise_activity(transactions, after_date=config.last_txn_on)
        outstanding, source = next_outstanding(
            current, activity, first_sync=first_sync
        )
        latest_repayment = activity.latest_repayment_gbp or config.minimum_payment_gbp

        if outstanding is None:
            await funding_circle_settings_service.mark_synced(
                db,
                source="needs_outstanding",
                outstanding_gbp=None,
                last_txn_on=activity.latest_date or config.last_txn_on,
                message="Enter the current outstanding once",
            )
            return FundingCircleSyncResult(
                imported=activity.count > 0,
                balance_gbp=0.0,
                repayments_applied_gbp=activity.repayment_gbp,
                source="needs_outstanding",
                message=(
                    "Found Funding Circle payments on the bank feed. Enter the "
                    "current outstanding once so later syncs can keep it current."
                ),
            )

        notes = "Imported from the connected bank feed"
        if activity.repayment_gbp:
            notes += f"; repayments {activity.repayment_gbp:.2f} GBP"
        await self._upsert_records(
            db,
            balance_gbp=outstanding,
            original_gbp=config.original_gbp or activity.drawdown_gbp or outstanding,
            apr_pct=config.apr_pct,
            minimum_payment_gbp=latest_repayment or config.minimum_payment_gbp,
            payment_day=config.payment_day,
            notes=notes,
        )
        await funding_circle_settings_service.mark_synced(
            db,
            source=source,
            outstanding_gbp=outstanding,
            last_txn_on=activity.latest_date or config.last_txn_on,
            message=notes,
        )
        return FundingCircleSyncResult(
            imported=True,
            balance_gbp=outstanding,
            repayments_applied_gbp=activity.repayment_gbp,
            source=source,
            message=notes,
        )

    async def _load_bank_transactions(self, db: AsyncSession) -> list[dict]:
        """Load Funding Circle activity from already-imported ledger rows."""
        rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.is_deleted.is_(False),
                    )
                )
            ).all()
        )
        transactions: list[dict] = []
        for row in rows:
            if not is_funding_circle_text(row.description):
                continue
            amount = (row.amount_pence or 0) / 100.0
            transactions.append(
                {
                    "description": row.description,
                    "amount": amount,
                    "transaction_type": "CREDIT" if amount > 0 else "DEBIT",
                    "timestamp": row.posted_on,
                    "date": row.posted_on,
                }
            )
        return transactions

    async def _existing_liability(self, db: AsyncSession) -> FinanceLiabilityRow | None:
        return await db.scalar(
            select(FinanceLiabilityRow).where(
                FinanceLiabilityRow.name == LOAN_NAME,
                FinanceLiabilityRow.scope == FinanceScope.BUSINESS.value,
                FinanceLiabilityRow.is_active.is_(True),
            )
        )

    async def _upsert_records(
        self,
        db: AsyncSession,
        *,
        balance_gbp: float,
        original_gbp: float | None,
        apr_pct: float,
        minimum_payment_gbp: float,
        payment_day: int | None,
        notes: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        account = await db.scalar(
            select(FinanceAccountRow).where(
                FinanceAccountRow.external_id == _EXTERNAL_ID,
                FinanceAccountRow.source == FinanceAccountSource.FUNDING_CIRCLE.value,
            )
        )
        if account is None:
            account = FinanceAccountRow(
                scope=FinanceScope.BUSINESS.value,
                account_type=FinanceAccountType.LOAN.value,
                name=LOAN_NAME,
                provider="Funding Circle",
                balance_gbp=balance_gbp,
                interest_rate_pct=apr_pct or None,
                minimum_payment_gbp=minimum_payment_gbp or None,
                notes=notes,
                source=FinanceAccountSource.FUNDING_CIRCLE.value,
                external_id=_EXTERNAL_ID,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(account)
            await db.flush()
        else:
            account.balance_gbp = balance_gbp
            account.notes = notes
            account.is_active = True
            if apr_pct:
                account.interest_rate_pct = apr_pct
            if minimum_payment_gbp:
                account.minimum_payment_gbp = minimum_payment_gbp
            account.updated_at = now

        liability = await self._existing_liability(db)
        if liability is None:
            db.add(
                FinanceLiabilityRow(
                    scope=FinanceScope.BUSINESS.value,
                    name=LOAN_NAME,
                    debt_type=DebtType.BUSINESS_LOAN.value,
                    balance_gbp=balance_gbp,
                    interest_rate_pct=apr_pct,
                    minimum_payment_gbp=minimum_payment_gbp,
                    original_balance_gbp=original_gbp or balance_gbp,
                    payment_day=payment_day,
                    account_id=account.id,
                    notes=notes,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            liability.balance_gbp = balance_gbp
            liability.notes = notes
            liability.account_id = account.id
            liability.is_active = True
            if apr_pct:
                liability.interest_rate_pct = apr_pct
            if minimum_payment_gbp:
                liability.minimum_payment_gbp = minimum_payment_gbp
            if original_gbp:
                liability.original_balance_gbp = original_gbp
            if payment_day:
                liability.payment_day = payment_day
            liability.updated_at = now
        await db.commit()


funding_circle_sync_service = FundingCircleSyncService()
