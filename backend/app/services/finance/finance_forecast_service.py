"""Month-end forecast: actuals + confirmed recurrings + optional history run-rate."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceRecurringRuleRow, FinanceTransactionRow
from app.services.finance.money import quantize_gbp

CONFIDENCE_OK = {"High", "Medium"}


def _month_bounds(month: str) -> tuple[str, str]:
    year, mon = [int(part) for part in month.split("-")]
    start = date(year, mon, 1)
    if mon == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, mon + 1, 1)
    last = end.toordinal() - 1
    return start.isoformat(), date.fromordinal(last).isoformat()


class FinanceForecastService:
    async def month_end(
        self,
        db: AsyncSession,
        *,
        month: str,
        scope: str,
        budget_gbp: float | None,
        category: str,
        actual_gbp: float | None,
        history_run_rate_gbp: float | None,
        history_confidence: str,
    ) -> dict[str, Any]:
        start, end = _month_bounds(month)
        today = datetime.now(timezone.utc).date().isoformat()
        remaining_recurring = 0.0
        rules = list(
            (
                await db.scalars(
                    select(FinanceRecurringRuleRow).where(
                        FinanceRecurringRuleRow.scope == scope,
                        FinanceRecurringRuleRow.status == "confirmed",
                        FinanceRecurringRuleRow.category == category,
                    )
                )
            ).all()
        )
        posted = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.scope == scope,
                        FinanceTransactionRow.category == category,
                        FinanceTransactionRow.is_deleted.is_(False),
                        FinanceTransactionRow.posted_on >= start,
                        FinanceTransactionRow.posted_on <= end,
                    )
                )
            ).all()
        )
        posted_descriptions = {row.description.strip().upper() for row in posted}
        for rule in rules:
            if rule.description.strip().upper() in posted_descriptions:
                continue
            remaining_recurring += float(rule.amount_gbp or 0)
        run_rate = None
        if history_run_rate_gbp is not None and history_confidence in CONFIDENCE_OK:
            run_rate = history_run_rate_gbp
        incurred = actual_gbp
        forecast = None
        if incurred is not None:
            forecast = incurred + remaining_recurring
            if run_rate is not None and incurred < run_rate:
                forecast = max(forecast, run_rate)
            forecast = quantize_gbp(forecast)
        return {
            "month": month,
            "scope": scope,
            "category": category,
            "actual_gbp": incurred,
            "forecast_gbp": forecast,
            "budget_gbp": budget_gbp,
            "confirmed_recurring_due_gbp": quantize_gbp(remaining_recurring) or 0.0,
            "history_run_rate_gbp": run_rate,
            "as_of": today,
            "labels": {
                "actual": "Actual",
                "forecast": "Forecast",
                "budget": "Budget",
            },
        }


finance_forecast_service = FinanceForecastService()
