"""Transparent Safe to Spend / available business cash calculations."""

from __future__ import annotations

from typing import Any

from app.services.finance.finance_calc import FinanceTotals, LiabilityView, SnapshotView
from app.services.finance.money import quantize_gbp


def _money(value: float) -> float:
    return float(quantize_gbp(value) or 0.0)


def compute_safe_to_spend(
    *,
    totals: FinanceTotals,
    personal: SnapshotView | None,
    business: SnapshotView | None,
    liabilities: list[LiabilityView],
    personal_buffer_gbp: float = 1000.0,
    business_buffer_gbp: float = 2000.0,
) -> dict[str, Any]:
    personal_income = float(getattr(personal, "monthly_income_gbp", 0) or 0)
    household = float(getattr(personal, "household_bills_gbp", 0) or 0)
    personal_spend = float(getattr(personal, "monthly_spending_gbp", 0) or 0)
    personal_debt_mins = sum(
        float(item.minimum_payment_gbp or 0)
        for item in liabilities
        if item.is_active and item.scope == "personal"
    )
    business_debt_mins = sum(
        float(item.minimum_payment_gbp or 0)
        for item in liabilities
        if item.is_active and item.scope == "business"
    )

    essentials = max(household, 0.0)
    if essentials <= 0 and personal_spend > 0:
        essentials = personal_spend * 0.6

    tax_vat = float(totals.vat_reserve_gbp or 0)
    tax_ct = float(totals.corp_tax_reserve_gbp or 0)
    business_expenses = float(getattr(business, "expenses_gbp", 0) or 0)
    turnover = float(getattr(business, "turnover_gbp", 0) or 0)
    vat_topup = 0.0
    ct_topup = 0.0
    if turnover > 0:
        vat_target_monthly = turnover * 0.16 / 3
        ct_target_monthly = max(turnover - business_expenses, 0) * 0.19 / 12
        vat_topup = max(vat_target_monthly - tax_vat / 3, 0)
        ct_topup = max(ct_target_monthly - tax_ct / 12, 0)

    personal_committed = essentials + personal_debt_mins + personal_buffer_gbp
    personal_safe = _money(personal_income - personal_committed)
    if personal_income <= 0 and personal_spend <= 0:
        personal_safe = 0.0
        personal_note = "No transaction history available"
    else:
        personal_note = "expected income − essentials − debt minimums − cash buffer"

    business_cash = float(totals.business_cash_gbp or 0)
    business_available = _money(
        business_cash
        - business_expenses
        - business_debt_mins
        - vat_topup
        - ct_topup
        - business_buffer_gbp
    )
    business_note = (
        "business cash − operating expenses − debt − VAT/CT reserve top-ups − buffer"
    )
    combined_safe = _money(personal_safe + max(business_available, 0))

    def status(cash: float, buffer: float, projected: float) -> str:
        if projected < 0 or cash < 0:
            return "PROJECTED_SHORTFALL"
        if cash < buffer * 0.5:
            return "LOW_CASH"
        if cash < buffer:
            return "CAUTION"
        return "HEALTHY"

    return {
        "personal": {
            "safe_to_spend_gbp": max(personal_safe, 0.0),
            "status": status(
                float(totals.personal_cash_gbp or 0), personal_buffer_gbp, personal_safe
            ),
            "breakdown": {
                "expected_income_gbp": _money(personal_income),
                "essential_bills_gbp": _money(essentials),
                "debt_minimums_gbp": _money(personal_debt_mins),
                "cash_buffer_gbp": _money(personal_buffer_gbp),
                "formula": personal_note,
            },
        },
        "business": {
            "available_business_cash_gbp": business_available,
            "status": status(
                business_cash, business_buffer_gbp, business_available
            ),
            "breakdown": {
                "business_cash_gbp": _money(business_cash),
                "operating_expenses_gbp": _money(business_expenses),
                "debt_minimums_gbp": _money(business_debt_mins),
                "vat_reserve_topup_gbp": _money(vat_topup),
                "corp_tax_reserve_topup_gbp": _money(ct_topup),
                "cash_buffer_gbp": _money(business_buffer_gbp),
                "vat_reserved_gbp": _money(tax_vat),
                "corp_tax_reserved_gbp": _money(tax_ct),
                "formula": business_note,
                "disclaimer": (
                    "VAT and corporation tax figures are planning estimates only "
                    "and do not replace accountant advice."
                ),
            },
        },
        "combined": {
            "safe_to_spend_gbp": max(combined_safe, 0.0),
            "status": status(
                float(totals.available_cash_gbp or 0),
                personal_buffer_gbp + business_buffer_gbp,
                combined_safe,
            ),
        },
    }
