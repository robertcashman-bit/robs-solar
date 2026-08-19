"""Persisted dashboard summary so login can return last known figures immediately."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BusinessFinanceSnapshotRow,
    CashflowForecastRow,
    FinanceAccountRow,
    FinanceBudgetPlanRow,
    FinanceInsightRow,
    FinanceLiabilityRow,
    FinanceOverviewCacheRow,
    MonthlyBudgetRow,
    PersonalFinanceSnapshotRow,
)
from app.schemas.finance import FinanceOverviewResponse

logger = logging.getLogger(__name__)

CACHE_TTL = timedelta(minutes=15)
# Bump when overview calculation rules change so stale payloads are discarded.
CACHE_VERSION = "4"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


class FinanceOverviewCacheService:
    async def fingerprint(self, db: AsyncSession) -> str:
        try:
            return await self._fingerprint(db)
        except Exception:
            logger.warning("Overview cache fingerprint failed", exc_info=True)
            return ""

    async def _fingerprint(self, db: AsyncSession) -> str:
        accounts = (
            await db.execute(
                select(
                    func.count(FinanceAccountRow.id),
                    func.coalesce(func.sum(FinanceAccountRow.balance_gbp), 0),
                    func.max(FinanceAccountRow.updated_at),
                ).where(FinanceAccountRow.is_active.is_(True))
            )
        ).one()
        debts = (
            await db.execute(
                select(
                    func.count(FinanceLiabilityRow.id),
                    func.coalesce(func.sum(FinanceLiabilityRow.balance_gbp), 0),
                    func.max(FinanceLiabilityRow.updated_at),
                ).where(FinanceLiabilityRow.is_active.is_(True))
            )
        ).one()
        personal_id = await db.scalar(select(func.max(PersonalFinanceSnapshotRow.id)))
        business_id = await db.scalar(select(func.max(BusinessFinanceSnapshotRow.id)))
        plan_stamp = (
            await db.execute(
                select(
                    func.max(FinanceBudgetPlanRow.id),
                    func.max(FinanceBudgetPlanRow.updated_at),
                ).where(FinanceBudgetPlanRow.is_active.is_(True))
            )
        ).one()
        budget_stamp = (
            await db.execute(
                select(func.count(MonthlyBudgetRow.id), func.max(MonthlyBudgetRow.updated_at))
            )
        ).one()
        cashflow_id = await db.scalar(select(func.max(CashflowForecastRow.id)))
        insight_count = await db.scalar(
            select(func.count(FinanceInsightRow.id)).where(
                FinanceInsightRow.status == "active"
            )
        )
        raw = "|".join(
            [
                CACHE_VERSION,
                str(accounts[0]),
                f"{float(accounts[1]):.2f}",
                _stamp(accounts[2]),
                str(debts[0]),
                f"{float(debts[1]):.2f}",
                _stamp(debts[2]),
                str(personal_id or 0),
                str(business_id or 0),
                str(plan_stamp[0] or 0),
                _stamp(plan_stamp[1]),
                str(budget_stamp[0] or 0),
                _stamp(budget_stamp[1]),
                str(cashflow_id or 0),
                str(insight_count or 0),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    async def read(
        self,
        db: AsyncSession,
        month: str,
        *,
        current_fingerprint: str | None = None,
    ) -> FinanceOverviewResponse | None:
        try:
            row = await db.get(FinanceOverviewCacheRow, month)
        except Exception:
            logger.warning("Overview cache read failed", exc_info=True)
            return None
        if row is None:
            return None
        generated = row.generated_at
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        stale = _now() - generated > CACHE_TTL
        fingerprint_mismatch = bool(
            current_fingerprint and row.fingerprint != current_fingerprint
        )
        # Source tables changed — do not serve last-known for a different ledger.
        if fingerprint_mismatch:
            return None
        try:
            payload = json.loads(row.payload_json)
            if "liquid_assets_gbp" not in payload:
                return None
            overview = FinanceOverviewResponse.model_validate(payload)
        except Exception:
            logger.warning("Overview cache payload was unreadable", exc_info=True)
            return None
        # TTL expiry alone still returns last Neon/local figures so login paint
        # is not gated on a full recompute; callers refresh in the background.
        if stale:
            logger.info("Serving soft-stale overview cache for month=%s", month)
        overview.cached = True
        overview.generated_at = row.generated_at
        return overview

    async def write(
        self,
        db: AsyncSession,
        month: str,
        overview: FinanceOverviewResponse,
        fingerprint: str,
    ) -> None:
        now = _now()
        overview.generated_at = now
        overview.cached = False
        payload = overview.model_dump(mode="json")
        row = await db.get(FinanceOverviewCacheRow, month)
        encoded = json.dumps(payload, default=str)
        if row is None:
            db.add(
                FinanceOverviewCacheRow(
                    month=month,
                    payload_json=encoded,
                    fingerprint=fingerprint,
                    generated_at=now,
                )
            )
        else:
            row.payload_json = encoded
            row.fingerprint = fingerprint
            row.generated_at = now
        try:
            await db.commit()
        except Exception:
            logger.warning("Could not persist overview cache", exc_info=True)
            await db.rollback()

    async def clear(self, db: AsyncSession, month: str | None = None) -> None:
        if month:
            row = await db.get(FinanceOverviewCacheRow, month)
            if row is not None:
                await db.delete(row)
        else:
            rows = (await db.scalars(select(FinanceOverviewCacheRow))).all()
            for row in rows:
                await db.delete(row)
        try:
            await db.commit()
        except Exception:
            await db.rollback()


finance_overview_cache_service = FinanceOverviewCacheService()
