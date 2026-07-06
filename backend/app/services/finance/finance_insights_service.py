"""Rule-based finance and energy insights."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailySavingsRow, FinanceInsightRow, PersonalFinanceSnapshotRow
from app.schemas.finance import (
    FinanceInsight,
    FinanceInsightCategory,
    FinanceInsightSeverity,
    FinanceOverviewResponse,
)


def _to_schema(row: FinanceInsightRow) -> FinanceInsight:
    return FinanceInsight(
        id=row.id,
        category=FinanceInsightCategory(row.category),
        severity=FinanceInsightSeverity(row.severity),
        title=row.title,
        message=row.message,
        status=row.status,
        related_date=row.related_date,
        metadata=json.loads(row.metadata_json or "{}"),
        created_at=row.created_at,
    )


class FinanceInsightsService:
    async def refresh_for_overview(
        self,
        db: AsyncSession,
        overview: FinanceOverviewResponse,
    ) -> list[FinanceInsight]:

        await self._refresh_insights(db, overview)
        rows = await db.scalars(
            select(FinanceInsightRow)
            .where(FinanceInsightRow.status == "active")
            .order_by(FinanceInsightRow.created_at.desc())
            .limit(20)
        )
        return [_to_schema(r) for r in rows.all()]

    async def generate_and_list(self, db: AsyncSession) -> list[FinanceInsight]:
        rows = await db.scalars(
            select(FinanceInsightRow)
            .where(FinanceInsightRow.status == "active")
            .order_by(FinanceInsightRow.created_at.desc())
            .limit(20)
        )
        return [_to_schema(r) for r in rows.all()]

    async def dismiss(self, db: AsyncSession, insight_id: int) -> bool:
        row = await db.get(FinanceInsightRow, insight_id)
        if row is None:
            return False
        row.status = "dismissed"
        row.dismissed_at = datetime.now(timezone.utc)
        await db.commit()
        return True

    async def _refresh_insights(self, db: AsyncSession, overview) -> None:
        """Replace stale active insights with freshly computed rules."""
        await db.execute(delete(FinanceInsightRow).where(FinanceInsightRow.status == "active"))

        candidates: list[tuple[str, str, str, str]] = []

        if overview.cash_after_bills_gbp < 500:
            candidates.append(
                (
                    FinanceInsightCategory.CASHFLOW.value,
                    FinanceInsightSeverity.WARNING.value,
                    "Personal cash may be tight after expected bills",
                    f"After household bills, about {overview.cash_after_bills_gbp:.0f} GBP "
                    "remains in personal accounts.",
                )
            )

        if overview.vat_reserve_warning:
            candidates.append(
                (
                    FinanceInsightCategory.TAX.value,
                    FinanceInsightSeverity.WARNING.value,
                    "Business VAT reserve appears low",
                    f"VAT reserve is {overview.vat_reserve_gbp:.0f} GBP — "
                    "consider topping up before the next return.",
                )
            )

        if overview.corp_tax_reserve_warning:
            candidates.append(
                (
                    FinanceInsightCategory.TAX.value,
                    FinanceInsightSeverity.INFO.value,
                    "Corporation tax reserve may be low",
                    f"Corp tax reserve is {overview.corp_tax_reserve_gbp:.0f} GBP "
                    "relative to estimated profit.",
                )
            )

        prior_snap = await db.scalar(
            select(PersonalFinanceSnapshotRow)
            .order_by(PersonalFinanceSnapshotRow.snapshot_date.desc())
            .offset(1)
            .limit(1)
        )
        if prior_snap and overview.credit_card_balances_gbp > prior_snap.monthly_spending_gbp * 0.5:
            candidates.append(
                (
                    FinanceInsightCategory.DEBT.value,
                    FinanceInsightSeverity.WARNING.value,
                    "Credit card balances are increasing",
                    "Credit card total is high relative to recent spending — review repayments.",
                )
            )

        directors = overview.directors_loan_gbp
        if directors > 5000 and overview.business_bank_balance_gbp < directors * 0.5:
            candidates.append(
                (
                    FinanceInsightCategory.BUSINESS.value,
                    FinanceInsightSeverity.WARNING.value,
                    "You may be drawing too much from the business this month",
                    f"Director's loan balance is {directors:.0f} GBP "
                    "while business cash is limited.",
                )
            )

        # Energy insights from daily savings
        savings_rows = await db.scalars(
            select(DailySavingsRow).order_by(DailySavingsRow.date.desc()).limit(7)
        )
        recent = list(savings_rows.all())
        if recent:
            avg_saving = sum(r.estimated_saving_gbp for r in recent) / len(recent)
            latest = recent[0]
            if latest.estimated_saving_gbp < avg_saving * 0.6:
                candidates.append(
                    (
                        FinanceInsightCategory.ENERGY.value,
                        FinanceInsightSeverity.INFO.value,
                        "Solar savings this month are below forecast",
                        f"Latest daily saving ({latest.estimated_saving_gbp:.2f} GBP) "
                        "is below the 7-day average.",
                    )
                )
            warnings = json.loads(latest.warnings_json or "[]")
            for w in warnings:
                text = (
                    f"{w.get('title', '')} {w.get('message', '')}"
                    if isinstance(w, dict)
                    else str(w)
                )
                if "discharg" in text.lower() or "peak" in text.lower():
                    candidates.append(
                        (
                            FinanceInsightCategory.ENERGY.value,
                            FinanceInsightSeverity.WARNING.value,
                            "Battery did not discharge during peak rate",
                            text.strip(),
                        )
                    )
                    break

        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        for category, severity, title, message in candidates:
            db.add(
                FinanceInsightRow(
                    category=category,
                    severity=severity,
                    title=title,
                    message=message,
                    status="active",
                    related_date=today,
                    metadata_json="{}",
                    created_at=now,
                )
            )
        await db.commit()


finance_insights_service = FinanceInsightsService()
