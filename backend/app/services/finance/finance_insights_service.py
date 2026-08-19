"""Rule-based finance insights."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceInsightRow, PersonalFinanceSnapshotRow
from app.schemas.finance import (
    FinanceInsight,
    FinanceInsightCategory,
    FinanceInsightSeverity,
    FinanceOverviewResponse,
)
from app.services.finance.money import format_gbp

CREDIT_CARD_INSIGHT_TITLE = "Credit card balances are high relative to spending"
_DISMISSED_TITLE_ALIASES = {
    CREDIT_CARD_INSIGHT_TITLE: frozenset({"Credit card balances are increasing"}),
}


def insight_title_is_dismissed(title: str, dismissed_titles: set[str]) -> bool:
    if title in dismissed_titles:
        return True
    aliases = _DISMISSED_TITLE_ALIASES.get(title, frozenset())
    return any(alias in dismissed_titles for alias in aliases)


def utilisation_is_high(used_gbp: float, credit_limit_gbp: float) -> bool:
    """True only when a recorded limit exists and at least 70% is drawn."""
    if credit_limit_gbp <= 0 or used_gbp <= 0:
        return False
    return used_gbp / credit_limit_gbp >= 0.7


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
            .where(FinanceInsightRow.category != FinanceInsightCategory.ENERGY.value)
            .order_by(FinanceInsightRow.created_at.desc())
            .limit(20)
        )
        return [_to_schema(r) for r in rows.all()]

    async def generate_and_list(self, db: AsyncSession) -> list[FinanceInsight]:
        rows = await db.scalars(
            select(FinanceInsightRow)
            .where(FinanceInsightRow.status == "active")
            .where(FinanceInsightRow.category != FinanceInsightCategory.ENERGY.value)
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
        dismissed_rows = await db.scalars(
            select(FinanceInsightRow).where(FinanceInsightRow.status == "dismissed")
        )
        dismissed_titles = {row.title for row in dismissed_rows.all()}

        candidates: list[tuple[str, str, str, str]] = []

        if overview.monthly_surplus_gbp < 0:
            candidates.append(
                (
                    FinanceInsightCategory.CASHFLOW.value,
                    FinanceInsightSeverity.CRITICAL.value,
                    "Negative monthly cashflow",
                    f"Recorded spending and debt repayments exceed income by "
                    f"{format_gbp(abs(overview.monthly_surplus_gbp))}. "
                    "Adjust the budget or income snapshot.",
                )
            )

        if overview.personal_overdraft_gbp > 0:
            candidates.append(
                (
                    FinanceInsightCategory.CASHFLOW.value,
                    FinanceInsightSeverity.WARNING.value,
                    "Personal current account is overdrawn",
                    f"Personal overdraft is {format_gbp(overview.personal_overdraft_gbp)}. "
                    "Clear this before increasing discretionary spending.",
                )
            )

        if overview.cash_after_bills_gbp < 500:
            candidates.append(
                (
                    FinanceInsightCategory.CASHFLOW.value,
                    FinanceInsightSeverity.WARNING.value,
                    "Personal cash may be tight after expected bills",
                    f"After household bills and any overdraft, about "
                    f"{format_gbp(overview.cash_after_bills_gbp)} remains in personal accounts.",
                )
            )

        if overview.active_budget and overview.active_budget.surplus_gbp < 0:
            candidates.append(
                (
                    FinanceInsightCategory.CASHFLOW.value,
                    FinanceInsightSeverity.WARNING.value,
                    "Active budget is in deficit",
                    f"{overview.active_budget.name} projects a shortfall of "
                    f"{format_gbp(abs(overview.active_budget.surplus_gbp))}.",
                )
            )

        if utilisation_is_high(overview.credit_card_balances_gbp, overview.credit_limit_gbp):
            used = overview.credit_card_balances_gbp
            limit = overview.credit_limit_gbp
            candidates.append(
                (
                    FinanceInsightCategory.DEBT.value,
                    FinanceInsightSeverity.WARNING.value,
                    "Credit utilisation is high",
                    f"Revolving balances are {format_gbp(used)} of {format_gbp(limit)} limit.",
                )
            )

        if overview.vat_reserve_warning:
            candidates.append(
                (
                    FinanceInsightCategory.TAX.value,
                    FinanceInsightSeverity.WARNING.value,
                    "Business VAT reserve appears low",
                    f"VAT reserve is {format_gbp(overview.vat_reserve_gbp)} — "
                    "consider topping up before the next return.",
                )
            )

        if overview.corp_tax_reserve_warning:
            candidates.append(
                (
                    FinanceInsightCategory.TAX.value,
                    FinanceInsightSeverity.INFO.value,
                    "Corporation tax reserve may be low",
                    f"Corp tax reserve is {format_gbp(overview.corp_tax_reserve_gbp)} "
                    "relative to estimated profit.",
                )
            )

        safe = getattr(overview, "safe_to_spend", None) or {}
        personal_safe = safe.get("personal") or {}
        if personal_safe.get("status") in {"LOW_CASH", "PROJECTED_SHORTFALL"}:
            amount = float(personal_safe.get("safe_to_spend_gbp") or 0)
            candidates.append(
                (
                    FinanceInsightCategory.CASHFLOW.value,
                    FinanceInsightSeverity.WARNING.value,
                    "Available discretionary spending is limited",
                    f"Safe to spend this month is about {format_gbp(amount)} after essentials, "
                    "debt minimums and your cash buffer.",
                )
            )
        business_safe = safe.get("business") or {}
        biz_break = business_safe.get("breakdown") or {}
        vat_short = float(biz_break.get("vat_reserve_topup_gbp") or 0)
        if vat_short > 50:
            candidates.append(
                (
                    FinanceInsightCategory.TAX.value,
                    FinanceInsightSeverity.INFO.value,
                    "VAT reserve may need a monthly top-up",
                    f"Suggested VAT reserve top-up is about {format_gbp(vat_short)} this month "
                    "(planning estimate only — not tax advice).",
                )
            )

        prior_snap = await db.scalar(
            select(PersonalFinanceSnapshotRow)
            .order_by(PersonalFinanceSnapshotRow.snapshot_date.desc())
            .offset(1)
            .limit(1)
        )
        if (
            prior_snap
            and overview.credit_card_balances_gbp > prior_snap.monthly_spending_gbp * 0.5
        ):
            candidates.append(
                (
                    FinanceInsightCategory.DEBT.value,
                    FinanceInsightSeverity.WARNING.value,
                    CREDIT_CARD_INSIGHT_TITLE,
                    "Credit card total is high relative to recent spending — "
                    "review repayments.",
                )
            )

        directors = overview.directors_loan_gbp
        if directors > 5000 and overview.business_bank_balance_gbp < directors * 0.5:
            candidates.append(
                (
                    FinanceInsightCategory.BUSINESS.value,
                    FinanceInsightSeverity.INFO.value,
                    "The company owes you on the director's loan",
                    f"Director's loan is {format_gbp(directors)} owed to you. "
                    "Business cash is lower than that claim — keep enough in "
                    "the company if you plan to draw it.",
                )
            )

        actions = {
            FinanceInsightCategory.CASHFLOW.value: ("/finance/budget", "Adjust budget"),
            FinanceInsightCategory.DEBT.value: ("/finance/debts", "Edit debt"),
            FinanceInsightCategory.TAX.value: ("/finance/business", "Review reserves"),
            FinanceInsightCategory.BUSINESS.value: ("/finance/business", "Review business"),
        }
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()
        for category, severity, title, message in candidates:
            if insight_title_is_dismissed(title, dismissed_titles):
                continue
            href, label = actions.get(category, ("/finance/personal", "Review"))
            if "APR" in title or "APR" in message:
                href, label = "/finance/debts", "Add APR"
            if "budget" in title.lower():
                href, label = "/finance/budget", "Adjust budget"
            db.add(
                FinanceInsightRow(
                    category=category,
                    severity=severity,
                    title=title,
                    message=message,
                    status="active",
                    related_date=today,
                    metadata_json=json.dumps({"action_href": href, "action_label": label}),
                    created_at=now,
                )
            )
        await db.commit()


finance_insights_service = FinanceInsightsService()
