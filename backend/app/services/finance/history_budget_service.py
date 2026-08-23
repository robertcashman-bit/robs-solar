"""Generate a budget from stored transactions only. Never invent amounts."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceTransactionRow
from app.schemas.finance import (
    BudgetPlanCreate,
    BudgetPlanFromHistory,
    BudgetPlanLineWrite,
    BudgetStyle,
    FinanceScope,
)
from app.services.finance.category_registry import apply_confirmed_rules, list_confirmed_rules
from app.services.finance.finance_budget_plan_service import finance_budget_plan_service
from app.services.finance.money import from_pence, quantize_gbp

# Primary blend favours multi-year history when enough months exist.
WINDOW_WEIGHTS = {36: 0.40, 12: 0.35, 6: 0.25}
# Short personal feeds (e.g. ~3 months of Lunch Flow) still produce a plan.
SHORT_FALLBACK_WEIGHTS = {3: 1.0}
MIN_MONTHS = {36: 12, 12: 6, 6: 3, 3: 2}
# How far back the earliest txn must reach for a window to qualify.
# 36m accepts 24m+ of coverage so multi-year QuickFile imports are used even
# when the full 36 calendar months are not yet filled.
COVERAGE_MONTHS = {36: 24, 12: 12, 6: 6, 3: 3}

# Named one-off categories — excluded from typical averaging and surfaced on a
# separate one-offs line. Statistical outlier fencing still applies elsewhere.
_ONE_OFF_CATEGORY_HINTS = (
    "solar",
    "vat pot",
    "vat transfer",
    "vat transfers",
    "large invoice",
    "unusual invoice",
    "one-off",
    "one off",
    "capex",
    "installation",
)


def is_named_one_off_category(category: str) -> bool:
    text = (category or "").strip().lower()
    if not text:
        return False
    return any(hint in text for hint in _ONE_OFF_CATEGORY_HINTS)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, months: int) -> date:
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def _distinct_months(dates: list[str], start: str, end: str) -> set[str]:
    return {item[:7] for item in dates if start <= item <= end}


def _coefficient_of_variation(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = statistics.fmean(values)
    if mean == 0:
        return None
    return statistics.pstdev(values) / abs(mean)


def _confidence(*, month_count: int, txn_count: int, cv: float | None, recurring: bool) -> str:
    if month_count < 2 or txn_count < 2:
        return "Insufficient data"
    if recurring and month_count >= 3 and (cv is None or cv <= 0.25):
        return "High"
    # Multi-year coverage can still be High/Medium with slightly looser CV.
    if month_count >= 24 and txn_count >= 12 and (cv is None or cv <= 0.55):
        return "High"
    if month_count >= 12 and txn_count >= 6 and (cv is None or cv <= 0.50):
        return "High"
    if month_count >= 6 and txn_count >= 6 and (cv is None or cv <= 0.45):
        return "High"
    if month_count >= 12 and txn_count >= 6 and (cv is None or cv <= 0.80):
        return "Medium"
    if month_count >= 3 and txn_count >= 3 and (cv is None or cv <= 0.75):
        return "Medium"
    return "Low"


def _annual_provision(posted_on: list[str], amounts: list[int]) -> dict[str, Any] | None:
    if len(posted_on) < 2:
        return None
    parsed = sorted(date.fromisoformat(item) for item in posted_on)
    gaps = [(parsed[index] - parsed[index - 1]).days for index in range(1, len(parsed))]
    annual_gaps = [gap for gap in gaps if 334 <= gap <= 396]
    if len(annual_gaps) < 1 or len(annual_gaps) < len(gaps) / 2:
        return None
    typical = from_pence(int(round(sum(abs(value) for value in amounts) / len(amounts))))
    monthly = quantize_gbp(typical / 12) or 0.0
    return {
        "kind": "annual_provision",
        "occurrences": len(parsed),
        "typical_gbp": typical,
        "formula": f"{typical} / 12",
        "monthly_gbp": monthly,
    }


class HistoryBudgetService:
    async def preview(self, db: AsyncSession, scope: str) -> dict[str, Any]:
        if scope not in {"personal", "business"}:
            raise ValueError("Scope must be personal or business")
        today = datetime.now(timezone.utc).date()
        rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.scope == scope,
                        FinanceTransactionRow.is_deleted.is_(False),
                        FinanceTransactionRow.is_transfer.is_(False),
                    )
                )
            ).all()
        )
        rules = await list_confirmed_rules(db)
        classified: list[tuple[FinanceTransactionRow, str]] = []
        uncategorised = 0
        for row in rows:
            category = (row.category or "").strip() or apply_confirmed_rules(
                row.description, scope, rules
            )
            if not category:
                uncategorised += 1
                continue
            classified.append((row, category))

        income_rows = [row for row, _ in classified if row.amount_pence > 0]
        expense_groups: dict[str, list[FinanceTransactionRow]] = defaultdict(list)
        one_off_groups: dict[str, list[FinanceTransactionRow]] = defaultdict(list)
        for row, category in classified:
            if row.amount_pence >= 0:
                continue
            if is_named_one_off_category(category):
                one_off_groups[category].append(row)
            else:
                expense_groups[category].append(row)

        lines = []
        for category, group in sorted(expense_groups.items()):
            lines.append(self._recommend_line(category, group, today, scope, "expense"))
        one_offs = []
        for category, group in sorted(one_off_groups.items()):
            total = from_pence(sum(-row.amount_pence for row in group))
            one_offs.append(
                {
                    "scope": scope,
                    "category": category,
                    "amount_gbp": total,
                    "txn_count": len(group),
                    "kind": "one_off",
                    "source_note": (
                        "Named one-off category — excluded from typical monthly average."
                    ),
                }
            )
        income_line = self._recommend_income(income_rows, today)
        return {
            "scope": scope,
            "transaction_count": len(rows),
            "categorised_count": len(classified),
            "uncategorised_count": uncategorised,
            "income": income_line,
            "lines": lines,
            "one_offs": one_offs,
            "insufficient": not lines and income_line["insufficient_data"],
            "explanation": (
                "Recommendations use stored transactions only (up to 36 months). "
                "Named one-off categories (solar, VAT pot / VAT transfer, large "
                "unusual invoices) are excluded from typical averages and listed "
                "separately. Exceptionally large one-off txs are also fenced before "
                "averaging. Uncategorised rows are excluded until you assign a "
                "category or confirm a rule. Personal and business stay separate, "
                "line-by-line from the category registry. Missing windows are "
                "dropped and remaining weights are renormalized."
            ),
        }

    def _collect_windows(
        self,
        group: list[FinanceTransactionRow],
        today: date,
        *,
        income: bool,
        weights: dict[int, float],
        earliest: str,
    ) -> dict[int, dict[str, Any]]:
        windows: dict[int, dict[str, Any]] = {}
        end = today.isoformat()
        for months, weight in weights.items():
            start = _add_months(_month_start(today), -(months - 1)).isoformat()
            coverage = COVERAGE_MONTHS.get(months, months)
            coverage_start = _add_months(
                _month_start(today), -(coverage - 1)
            ).isoformat()
            # Compare year-months so a mid-month earliest txn in the coverage
            # month still qualifies (day-of-month must not drop the window).
            if earliest and earliest[:7] > coverage_start[:7]:
                continue
            in_window = [row for row in group if start <= row.posted_on <= end]
            month_keys = _distinct_months([row.posted_on for row in in_window], start, end)
            if len(month_keys) < MIN_MONTHS[months]:
                continue
            total = sum(
                row.amount_pence if income else -row.amount_pence
                for row in in_window
            )
            average = from_pence(int(round(total / months)))
            windows[months] = {
                "months": months,
                "weight": weight,
                "average_gbp": average,
                "txn_count": len(in_window),
                "month_count": len(month_keys),
            }
        return windows

    def _window_averages(
        self, group: list[FinanceTransactionRow], today: date, *, income: bool
    ) -> dict[str, Any]:
        dates = [row.posted_on for row in group]
        earliest = min(dates) if dates else ""
        windows = self._collect_windows(
            group, today, income=income, weights=WINDOW_WEIGHTS, earliest=earliest
        )
        if not windows:
            windows = self._collect_windows(
                group,
                today,
                income=income,
                weights=SHORT_FALLBACK_WEIGHTS,
                earliest=earliest,
            )
        if not windows:
            return {"available": {}, "recommended_gbp": None, "weights": {}, "formula": ""}
        total_weight = sum(item["weight"] for item in windows.values())
        renormalized = {
            months: item["weight"] / total_weight for months, item in windows.items()
        }
        recommended = 0.0
        parts = []
        for months, item in windows.items():
            share = renormalized[months]
            recommended += item["average_gbp"] * share
            parts.append(f"{item['average_gbp']}×{round(share, 4)} ({months}m)")
        return {
            "available": windows,
            "recommended_gbp": quantize_gbp(recommended),
            "weights": {str(key): value for key, value in renormalized.items()},
            "formula": " + ".join(parts),
        }

    def _recommend_line(
        self,
        category: str,
        group: list[FinanceTransactionRow],
        today: date,
        scope: str,
        kind: str,
    ) -> dict[str, Any]:
        from app.services.finance.finance_history_stats import (
            classify_volatility,
            exclude_outlier_transactions,
            median_gbp,
            remove_outliers,
        )

        filtered, _outlier_txs, outlier_meta = exclude_outlier_transactions(group)
        annual = _annual_provision(
            [row.posted_on for row in filtered],
            [row.amount_pence for row in filtered],
        )
        windowed = self._window_averages(filtered, today, income=kind == "income")
        monthly_totals: dict[str, float] = defaultdict(float)
        for row in filtered:
            monthly_totals[row.posted_on[:7]] += from_pence(
                row.amount_pence if kind == "income" else -row.amount_pence
            )
        cv = _coefficient_of_variation(list(monthly_totals.values()))
        excluded_txs = int(outlier_meta.get("excluded_count") or 0)
        if annual and (windowed["recommended_gbp"] is None or annual["monthly_gbp"] > 0):
            amount = annual["monthly_gbp"]
            basis = {
                **annual,
                "outlier_txs_excluded": excluded_txs,
                "txn_count": len(filtered),
                "txn_count_before_outliers": len(group),
            }
            confidence = _confidence(
                month_count=len(monthly_totals),
                txn_count=len(filtered),
                cv=cv,
                recurring=True,
            )
        elif windowed["recommended_gbp"] is not None:
            series = list(monthly_totals.values())
            kept, outliers = remove_outliers(series)
            med = median_gbp(kept or series)
            volatility = classify_volatility(cv, recurring=False)
            amount = windowed["recommended_gbp"]
            if volatility in {"VARIABLE", "EXCEPTIONAL"} and med > 0:
                amount = med
            basis = {
                "kind": (
                    "weighted_average"
                    if volatility not in {"VARIABLE", "EXCEPTIONAL"}
                    else "median"
                ),
                "windows": windowed["available"],
                "weights": windowed["weights"],
                "formula": windowed["formula"],
                "txn_count": len(filtered),
                "txn_count_before_outliers": len(group),
                "outlier_txs_excluded": excluded_txs,
                "median_gbp": med,
                "volatility": volatility,
                "outlier_months": len(outliers),
                "trend_note": (
                    "Volatile categories use median so one-offs do not distort the budget."
                    if volatility in {"VARIABLE", "EXCEPTIONAL"}
                    else "Weighted multi-window average of stored months."
                ),
            }
            confidence = _confidence(
                month_count=len(monthly_totals),
                txn_count=len(filtered),
                cv=cv,
                recurring=False,
            )
        else:
            amount = 0.0
            basis = {
                "kind": "insufficient",
                "txn_count": len(filtered),
                "txn_count_before_outliers": len(group),
                "outlier_txs_excluded": excluded_txs,
            }
            confidence = "Insufficient data"

        if outlier_meta.get("unsafe"):
            basis["outlier_filter_unsafe"] = True
            basis["would_exclude_txs"] = int(outlier_meta.get("would_exclude_count") or 0)
            if confidence != "Insufficient data":
                confidence = "Low"

        insufficient = confidence == "Insufficient data" or amount is None
        source_note = basis.get("formula") or (
            "Insufficient stored history" if insufficient else "History average"
        )
        if excluded_txs:
            source_note = f"{source_note}; excluded {excluded_txs} exceptional txn(s)"
        outlier_months = int(basis.get("outlier_months") or 0)
        if outlier_months:
            source_note = f"{source_note}; excluded {outlier_months} outlier month(s)"
        if outlier_meta.get("unsafe"):
            source_note = (
                f"{source_note}; exceptional filter unsafe — kept original "
                f"{len(group)} txn(s)"
            )
        return {
            "scope": scope,
            "category": category,
            "amount_gbp": 0.0 if insufficient else float(amount or 0),
            "confidence": confidence,
            "insufficient_data": insufficient,
            "basis_json": json.dumps(basis, default=str),
            "source": "history",
            "source_note": source_note,
        }

    def _recommend_income(self, rows: list[FinanceTransactionRow], today: date) -> dict[str, Any]:
        from app.services.finance.finance_history_stats import exclude_outlier_transactions

        filtered, _outlier_txs, outlier_meta = exclude_outlier_transactions(rows)
        windowed = self._window_averages(filtered, today, income=True)
        monthly_totals: dict[str, float] = defaultdict(float)
        for row in filtered:
            monthly_totals[row.posted_on[:7]] += from_pence(row.amount_pence)
        cv = _coefficient_of_variation(list(monthly_totals.values()))
        excluded_txs = int(outlier_meta.get("excluded_count") or 0)
        if windowed["recommended_gbp"] is None:
            return {
                "amount_gbp": 0.0,
                "insufficient_data": True,
                "confidence": "Insufficient data",
                "basis_json": json.dumps(
                    {
                        "kind": "insufficient",
                        "txn_count": len(filtered),
                        "txn_count_before_outliers": len(rows),
                        "outlier_txs_excluded": excluded_txs,
                    }
                ),
            }
        confidence = _confidence(
            month_count=len(monthly_totals),
            txn_count=len(filtered),
            cv=cv,
            recurring=False,
        )
        if outlier_meta.get("unsafe") and confidence != "Insufficient data":
            confidence = "Low"
        basis = {
            "kind": "weighted_average",
            "windows": windowed["available"],
            "weights": windowed["weights"],
            "formula": windowed["formula"],
            "txn_count": len(filtered),
            "txn_count_before_outliers": len(rows),
            "outlier_txs_excluded": excluded_txs,
        }
        if outlier_meta.get("unsafe"):
            basis["outlier_filter_unsafe"] = True
            basis["would_exclude_txs"] = int(outlier_meta.get("would_exclude_count") or 0)
        return {
            "amount_gbp": float(windowed["recommended_gbp"] or 0),
            "insufficient_data": confidence == "Insufficient data",
            "confidence": confidence,
            "basis_json": json.dumps(basis, default=str),
        }

    async def create_plan(self, db: AsyncSession, body: BudgetPlanFromHistory):
        preview = await self.preview(db, body.scope.value)
        income = preview["income"]
        lines = [
            BudgetPlanLineWrite(
                scope=FinanceScope(body.scope.value),
                category=item["category"],
                amount_gbp=item["amount_gbp"],
                source="history",
                source_note=item["source_note"],
                is_custom=False,
                sort_order=index * 10,
                subcategory="",
                basis_json=item["basis_json"],
                confidence=item["confidence"],
                insufficient_data=item["insufficient_data"],
            )
            for index, item in enumerate(preview["lines"])
        ]
        name = body.name or f"{body.scope.value.title()} history budget"
        plan = await finance_budget_plan_service.create(
            db,
            BudgetPlanCreate(
                name=name,
                style=BudgetStyle.CUSTOM,
                origin="history",
                notes=preview["explanation"],
                explanation=preview["explanation"],
                income_gbp=income["amount_gbp"],
                lines=lines,
                active_scope=body.scope.value,
            ),
        )
        if body.activate:
            activated = await finance_budget_plan_service.activate(
                db, plan.id, scope=body.scope.value
            )
            return activated or plan
        return plan


history_budget_service = HistoryBudgetService()
