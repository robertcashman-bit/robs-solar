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

WINDOW_WEIGHTS = {3: 0.50, 6: 0.30, 12: 0.20}
MIN_MONTHS = {3: 2, 6: 3, 12: 6}


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
    if month_count >= 6 and txn_count >= 6 and (cv is None or cv <= 0.45):
        return "High"
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
        for row, category in classified:
            if row.amount_pence < 0:
                expense_groups[category].append(row)

        lines = []
        for category, group in sorted(expense_groups.items()):
            lines.append(self._recommend_line(category, group, today, scope, "expense"))
        income_line = self._recommend_income(income_rows, today)
        return {
            "scope": scope,
            "transaction_count": len(rows),
            "categorised_count": len(classified),
            "uncategorised_count": uncategorised,
            "income": income_line,
            "lines": lines,
            "insufficient": not lines and income_line["insufficient_data"],
            "explanation": (
                "Recommendations use stored transactions only. Uncategorised rows "
                "are excluded until you assign a category or confirm a rule. "
                "Missing windows are dropped and remaining weights are renormalized."
            ),
        }

    def _window_averages(
        self, group: list[FinanceTransactionRow], today: date, *, income: bool
    ) -> dict[str, Any]:
        dates = [row.posted_on for row in group]
        earliest = min(dates) if dates else ""
        windows: dict[int, dict[str, Any]] = {}
        for months, weight in WINDOW_WEIGHTS.items():
            start = _add_months(_month_start(today), -(months - 1)).isoformat()
            end = today.isoformat()
            if earliest and earliest > start:
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
        annual = _annual_provision(
            [row.posted_on for row in group],
            [row.amount_pence for row in group],
        )
        windowed = self._window_averages(group, today, income=kind == "income")
        monthly_totals: dict[str, float] = defaultdict(float)
        for row in group:
            monthly_totals[row.posted_on[:7]] += from_pence(
                row.amount_pence if kind == "income" else -row.amount_pence
            )
        cv = _coefficient_of_variation(list(monthly_totals.values()))
        if annual and (windowed["recommended_gbp"] is None or annual["monthly_gbp"] > 0):
            amount = annual["monthly_gbp"]
            basis = annual
            confidence = _confidence(
                month_count=len(monthly_totals),
                txn_count=len(group),
                cv=cv,
                recurring=True,
            )
        elif windowed["recommended_gbp"] is not None:
            amount = windowed["recommended_gbp"]
            basis = {
                "kind": "weighted_average",
                "windows": windowed["available"],
                "weights": windowed["weights"],
                "formula": windowed["formula"],
                "txn_count": len(group),
            }
            confidence = _confidence(
                month_count=len(monthly_totals),
                txn_count=len(group),
                cv=cv,
                recurring=False,
            )
        else:
            amount = 0.0
            basis = {"kind": "insufficient", "txn_count": len(group)}
            confidence = "Insufficient data"
        insufficient = confidence == "Insufficient data" or amount is None
        return {
            "scope": scope,
            "category": category,
            "amount_gbp": 0.0 if insufficient else float(amount or 0),
            "confidence": confidence,
            "insufficient_data": insufficient,
            "basis_json": json.dumps(basis, default=str),
            "source": "history",
            "source_note": basis.get("formula")
            or ("Insufficient stored history" if insufficient else "History average"),
        }

    def _recommend_income(self, rows: list[FinanceTransactionRow], today: date) -> dict[str, Any]:
        windowed = self._window_averages(rows, today, income=True)
        monthly_totals: dict[str, float] = defaultdict(float)
        for row in rows:
            monthly_totals[row.posted_on[:7]] += from_pence(row.amount_pence)
        cv = _coefficient_of_variation(list(monthly_totals.values()))
        if windowed["recommended_gbp"] is None:
            return {
                "amount_gbp": 0.0,
                "insufficient_data": True,
                "confidence": "Insufficient data",
                "basis_json": json.dumps({"kind": "insufficient", "txn_count": len(rows)}),
            }
        confidence = _confidence(
            month_count=len(monthly_totals),
            txn_count=len(rows),
            cv=cv,
            recurring=False,
        )
        return {
            "amount_gbp": float(windowed["recommended_gbp"] or 0),
            "insufficient_data": confidence == "Insufficient data",
            "confidence": confidence,
            "basis_json": json.dumps(
                {
                    "kind": "weighted_average",
                    "windows": windowed["available"],
                    "weights": windowed["weights"],
                    "formula": windowed["formula"],
                    "txn_count": len(rows),
                },
                default=str,
            ),
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
