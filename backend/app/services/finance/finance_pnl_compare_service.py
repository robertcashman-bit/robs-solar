"""Stored-transaction P&L compare windows for Reports / Personal / Business."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.finance.finance_ledger_service import finance_ledger_service
from app.services.finance.finance_period import _add_months, parse_scope, period_window


class FinancePnlCompareService:
    async def compare(
        self,
        db: AsyncSession,
        *,
        scope: str,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        scope_key = parse_scope(scope, default="personal")
        if scope_key == "both":
            raise ValueError("pnl compare requires personal or business scope")
        today = as_of or datetime.now(timezone.utc).date()
        rows: list[dict[str, Any]] = []

        for key in ("1m", "3m", "6m"):
            window = period_window(key, as_of=today)
            current = await finance_ledger_service.period_flow_totals(
                db, period=key, scope=scope_key, as_of=today
            )
            # Prior window of the same length ending just before this one.
            prior_as_of = date.fromisoformat(window.date_from)
            prior = await finance_ledger_service.period_flow_totals(
                db, period=key, scope=scope_key, as_of=prior_as_of
            )
            prior_window = period_window(key, as_of=prior_as_of)
            rows.append(
                self._row(
                    key=key,
                    label=window.label,
                    current=current,
                    prior=prior,
                    compare_label=f"Prior {window.label.lower()}",
                    compare_from=prior_window.date_from,
                    compare_to=prior_window.date_to,
                )
            )

        # Last complete month vs the same calendar month one year earlier.
        last_month = period_window("1m", as_of=today)
        lm_start = date.fromisoformat(last_month.date_from)
        yoy_year, yoy_month = _add_months(lm_start.year, lm_start.month, -12)
        # period_window("1m") uses previous calendar month relative to as_of,
        # so as_of = first day of month after the YoY month.
        next_y, next_m = _add_months(yoy_year, yoy_month, 1)
        yoy_anchor = date(next_y, next_m, 1)
        current_lm = await finance_ledger_service.period_flow_totals(
            db, period="1m", scope=scope_key, as_of=today
        )
        prior_yoy = await finance_ledger_service.period_flow_totals(
            db, period="1m", scope=scope_key, as_of=yoy_anchor
        )
        yoy_window = period_window("1m", as_of=yoy_anchor)
        rows.append(
            self._row(
                key="smly",
                label=f"{last_month.label} vs same month last year",
                current=current_lm,
                prior=prior_yoy,
                compare_label="Same month last year",
                compare_from=yoy_window.date_from,
                compare_to=yoy_window.date_to,
            )
        )

        return {"scope": scope_key, "as_of": today.isoformat(), "rows": rows}

    @staticmethod
    def _row(
        *,
        key: str,
        label: str,
        current: dict[str, Any],
        prior: dict[str, Any],
        compare_label: str,
        compare_from: str,
        compare_to: str,
    ) -> dict[str, Any]:
        empty = int(current.get("transaction_count") or 0) == 0
        prior_empty = int(prior.get("transaction_count") or 0) == 0

        def _delta(a: Any, b: Any) -> float | None:
            if empty or prior_empty:
                return None
            return round(float(a or 0) - float(b or 0), 2)

        return {
            "key": key,
            "label": label,
            "date_from": current.get("date_from"),
            "date_to": current.get("date_to"),
            "income_gbp": current.get("income_gbp"),
            "spending_gbp": current.get("spending_gbp"),
            "surplus_gbp": current.get("surplus_gbp"),
            "transaction_count": current.get("transaction_count", 0),
            "coverage_note": current.get("coverage_note") or "",
            "empty": empty,
            "compare_label": compare_label,
            "compare_date_from": compare_from,
            "compare_date_to": compare_to,
            "compare_income_gbp": prior.get("income_gbp"),
            "compare_spending_gbp": prior.get("spending_gbp"),
            "compare_surplus_gbp": prior.get("surplus_gbp"),
            "compare_transaction_count": prior.get("transaction_count", 0),
            "compare_coverage_note": prior.get("coverage_note") or "",
            "compare_empty": prior_empty,
            "income_change_gbp": _delta(current.get("income_gbp"), prior.get("income_gbp")),
            "spending_change_gbp": _delta(
                current.get("spending_gbp"), prior.get("spending_gbp")
            ),
            "surplus_change_gbp": _delta(
                current.get("surplus_gbp"), prior.get("surplus_gbp")
            ),
        }


finance_pnl_compare_service = FinancePnlCompareService()
