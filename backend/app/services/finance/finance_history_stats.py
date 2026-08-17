"""Deterministic per-category historical statistics for budgeting."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceTransactionRow
from app.services.finance.money import from_pence, quantize_gbp


def _month_key(value: str) -> str:
    return value[:7]


def _add_months(year_month: str, delta: int) -> str:
    year = int(year_month[:4])
    month = int(year_month[5:7]) + delta
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return f"{year:04d}-{month:02d}"


def median_gbp(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(quantize_gbp(statistics.median(values)) or 0.0)


def trimmed_mean_gbp(values: list[float], trim_fraction: float = 0.1) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    drop = int(len(ordered) * trim_fraction)
    core = ordered[drop : len(ordered) - drop] if drop and len(ordered) > 2 * drop else ordered
    return float(quantize_gbp(statistics.fmean(core)) or 0.0)


def remove_outliers(values: list[float]) -> tuple[list[float], list[float]]:
    if len(values) < 4:
        return list(values), []
    ordered = sorted(values)
    q1 = statistics.median(ordered[: len(ordered) // 2])
    q3 = statistics.median(ordered[(len(ordered) + 1) // 2 :])
    iqr = q3 - q1
    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr
    kept = [value for value in values if low <= value <= high]
    outliers = [value for value in values if value < low or value > high]
    return kept, outliers


def classify_volatility(cv: float | None, *, recurring: bool) -> str:
    if recurring and (cv is None or cv <= 0.15):
        return "FIXED"
    if cv is None:
        return "VARIABLE"
    if cv <= 0.2:
        return "SEMI_FIXED"
    if cv >= 1.2:
        return "EXCEPTIONAL"
    return "VARIABLE"


class FinanceHistoryStatsService:
    async def category_stats(
        self,
        db: AsyncSession,
        *,
        scope: str,
        as_of: date | None = None,
    ) -> list[dict[str, Any]]:
        today = as_of or datetime.now(timezone.utc).date()
        current_month = today.strftime("%Y-%m")
        rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.scope == scope,
                        FinanceTransactionRow.is_deleted.is_(False),
                        FinanceTransactionRow.is_transfer.is_(False),
                        FinanceTransactionRow.amount_pence < 0,
                    )
                )
            ).all()
        )
        if not rows:
            return []

        by_category: dict[str, list[FinanceTransactionRow]] = defaultdict(list)
        for row in rows:
            category = (row.category or "").strip() or "Uncategorised"
            by_category[category].append(row)

        results: list[dict[str, Any]] = []
        for category, group in sorted(by_category.items()):
            monthly: dict[str, float] = defaultdict(float)
            for row in group:
                monthly[_month_key(row.posted_on)] += from_pence(abs(row.amount_pence))
            months_sorted = sorted(monthly.keys())
            series = [monthly[key] for key in months_sorted]
            kept, outliers = remove_outliers(series)
            cv = None
            if len(kept) >= 2 and statistics.fmean(kept) != 0:
                cv = statistics.pstdev(kept) / abs(statistics.fmean(kept))

            def window_avg(n: int) -> float | None:
                keys = [_add_months(current_month, -i) for i in range(n)]
                vals = [monthly[key] for key in keys if key in monthly]
                if len(vals) < max(1, n // 2):
                    return None
                return float(quantize_gbp(statistics.fmean(vals)) or 0.0)

            last_month = monthly.get(_add_months(current_month, -1), 0.0)
            med = median_gbp(kept or series)
            trend = 0.0
            if len(series) >= 4:
                recent = statistics.fmean(series[-3:])
                prior = (
                    statistics.fmean(series[-6:-3])
                    if len(series) >= 6
                    else statistics.fmean(series[:-3])
                )
                if prior:
                    trend = (recent - prior) / prior

            volatility = classify_volatility(cv, recurring=False)
            recommended = med
            if volatility == "VARIABLE":
                recommended = trimmed_mean_gbp(kept or series) or med
            elif volatility in {"FIXED", "SEMI_FIXED"} and series:
                recommended = series[-1] if volatility == "FIXED" else med
            if trend > 0.05:
                recommended = float(
                    quantize_gbp(recommended * (1 + min(trend, 0.25))) or recommended
                )

            results.append(
                {
                    "category": category,
                    "scope": scope,
                    "last_month_gbp": float(quantize_gbp(last_month) or 0.0),
                    "avg_3m_gbp": window_avg(3),
                    "avg_6m_gbp": window_avg(6),
                    "avg_12m_gbp": window_avg(12),
                    "min_gbp": float(quantize_gbp(min(series)) or 0.0) if series else 0.0,
                    "max_gbp": float(quantize_gbp(max(series)) or 0.0) if series else 0.0,
                    "median_gbp": med,
                    "trimmed_mean_gbp": trimmed_mean_gbp(kept or series),
                    "trend_pct": round(trend * 100, 1),
                    "volatility": volatility,
                    "outlier_months": len(outliers),
                    "month_count": len(series),
                    "recommended_budget_gbp": float(quantize_gbp(recommended) or 0.0),
                    "explain": {
                        "basis": volatility,
                        "median_gbp": med,
                        "trimmed_mean_gbp": trimmed_mean_gbp(kept or series),
                        "trend_pct": round(trend * 100, 1),
                        "outlier_months": len(outliers),
                        "recommended_gbp": float(quantize_gbp(recommended) or 0.0),
                    },
                }
            )
        return results

    async def explain_category(
        self,
        db: AsyncSession,
        *,
        scope: str,
        category: str,
    ) -> dict[str, Any]:
        stats = await self.category_stats(db, scope=scope)
        for item in stats:
            if item["category"].lower() == category.lower():
                return item
        return {
            "category": category,
            "scope": scope,
            "message": "No transaction history available",
            "explain": {"basis": "none", "recommended_gbp": 0.0},
        }


finance_history_stats_service = FinanceHistoryStatsService()
