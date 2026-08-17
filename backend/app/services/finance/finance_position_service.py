"""Persist monthly finance totals so reports can show real movement."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinancePositionSnapshotRow
from app.schemas.finance import (
    DebtHistoryPoint,
    FinanceOverviewResponse,
    FinancePositionSnapshot,
)


def _to_schema(row: FinancePositionSnapshotRow) -> FinancePositionSnapshot:
    return FinancePositionSnapshot(
        month=row.month,
        total_debt_gbp=row.total_debt_gbp,
        personal_debt_gbp=row.personal_debt_gbp,
        business_debt_gbp=row.business_debt_gbp,
        net_worth_gbp=row.net_worth_gbp,
        cash_available_gbp=row.cash_available_gbp,
        recorded_at=row.recorded_at,
    )


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


class FinancePositionService:
    async def record_from_overview(
        self,
        db: AsyncSession,
        overview: FinanceOverviewResponse,
        month: str | None = None,
    ) -> FinancePositionSnapshot | None:
        current_month = _current_month()
        month = month or current_month
        if month != current_month:
            # Live balances belong to this month only. Writing them into an
            # older key would overwrite real debt history when reports load
            # a previous month through get_overview.
            return await self.get_for_month(db, month)
        now = datetime.now(timezone.utc)
        row = await db.scalar(
            select(FinancePositionSnapshotRow).where(FinancePositionSnapshotRow.month == month)
        )
        if row is None:
            row = FinancePositionSnapshotRow(
                month=month,
                total_debt_gbp=overview.total_debt_gbp,
                personal_debt_gbp=overview.total_personal_debt_gbp,
                business_debt_gbp=overview.total_business_debt_gbp,
                net_worth_gbp=overview.net_worth_estimate_gbp,
                cash_available_gbp=overview.cash_available_gbp,
                recorded_at=now,
            )
            db.add(row)
        else:
            row.total_debt_gbp = overview.total_debt_gbp
            row.personal_debt_gbp = overview.total_personal_debt_gbp
            row.business_debt_gbp = overview.total_business_debt_gbp
            row.net_worth_gbp = overview.net_worth_estimate_gbp
            row.cash_available_gbp = overview.cash_available_gbp
            row.recorded_at = now
        await db.commit()
        await db.refresh(row)
        return _to_schema(row)

    async def get_for_month(
        self, db: AsyncSession, month: str
    ) -> FinancePositionSnapshot | None:
        row = await db.scalar(
            select(FinancePositionSnapshotRow).where(FinancePositionSnapshotRow.month == month)
        )
        return _to_schema(row) if row else None

    async def list_history(
        self, db: AsyncSession, limit: int = 24
    ) -> list[FinancePositionSnapshot]:
        rows = await db.scalars(
            select(FinancePositionSnapshotRow)
            .order_by(FinancePositionSnapshotRow.month.desc())
            .limit(limit)
        )
        # Newest N months, returned oldest→newest for charts.
        return [_to_schema(row) for row in reversed(rows.all())]

    async def get_latest_before(
        self, db: AsyncSession, month: str
    ) -> FinancePositionSnapshot | None:
        row = await db.scalar(
            select(FinancePositionSnapshotRow)
            .where(FinancePositionSnapshotRow.month < month)
            .order_by(FinancePositionSnapshotRow.month.desc())
            .limit(1)
        )
        return _to_schema(row) if row else None

    def as_debt_history(self, snapshots: list[FinancePositionSnapshot]) -> list[DebtHistoryPoint]:
        return [
            DebtHistoryPoint(month=item.month, total_debt_gbp=item.total_debt_gbp)
            for item in snapshots
        ]


finance_position_service = FinancePositionService()
