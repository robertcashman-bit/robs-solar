"""Parse QuickFile profit & loss and balance sheet report bodies."""

from __future__ import annotations

from typing import Any

# P&L breakdown section order and QuickFile-style labels.
_PL_SECTIONS: tuple[tuple[str, str, str, bool], ...] = (
    ("Turnover", "Turnover", "Turnover", False),
    ("LessCostofSales", "Less: Cost of sales", "LessCostofSales", True),
    ("LessExpenses", "Less: Expenses", "LessExpenses", True),
)

# Balance sheet breakdown section order and QuickFile-style labels.
_BS_SECTIONS: tuple[tuple[str, str, str, bool], ...] = (
    ("FixedAssets", "Fixed assets", "FixedAssets", False),
    ("CurrentAssets", "Current assets", "CurrentAssets", False),
    (
        "CurrentLiabilities",
        "Creditors: amounts falling due within one year",
        "CurrentLiabilities",
        True,
    ),
    (
        "LongTermLiabilities",
        "Creditors: amounts falling due after one year",
        "LongTermLiabilities",
        True,
    ),
    ("CapitalAndReserves", "Capital and reserves", "CapitalAndReserves", False),
)


def _balances_list(section: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not section:
        return []
    balances = section.get("Balances") or {}
    balance = balances.get("Balance")
    if balance is None:
        return []
    if isinstance(balance, list):
        return [item for item in balance if isinstance(item, dict)]
    if isinstance(balance, dict):
        return [balance]
    return []


def _float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _abs_cost(value: float) -> float:
    return round(abs(value), 2)


def _nominal_code(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return str(int(value))
    return str(value).strip() or None


def _line_amount(raw: float, *, use_abs: bool) -> float:
    return _abs_cost(raw) if use_abs else round(raw, 2)


def _parse_section_lines(
    section: dict[str, Any] | None,
    *,
    use_abs: bool,
) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for item in _balances_list(section):
        label = str(item.get("NominalAccountName") or "").strip()
        if not label:
            continue
        lines.append(
            {
                "nominal_code": _nominal_code(item.get("NominalCode")),
                "label": label,
                "amount_gbp": _line_amount(_float(item.get("Amount")), use_abs=use_abs),
            }
        )
    return lines


def _line_matches_label(label: str, *name_parts: str) -> bool:
    lowered = label.lower()
    return any(part.lower() in lowered for part in name_parts)


def _line_amount_from_breakdown(section: dict[str, Any] | None, *name_parts: str) -> float:
    for item in _balances_list(section):
        label = str(item.get("NominalAccountName") or "")
        if _line_matches_label(label, *name_parts):
            return round(abs(_float(item.get("Amount"))), 2)
    return 0.0


def _sum_lines_from_breakdown(section: dict[str, Any] | None, *name_parts: str) -> float:
    total = 0.0
    for item in _balances_list(section):
        label = str(item.get("NominalAccountName") or "")
        if _line_matches_label(label, *name_parts):
            total += round(abs(_float(item.get("Amount"))), 2)
    return round(total, 2)


def _liability_bucket_for_nominal(code: str | None) -> str | None:
    """UK-style chart: 2xxx are liabilities. 2100–2299 current; 2300+ long-term."""
    if not code:
        return None
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if not digits:
        return None
    # Live QuickFile may zero-pad ("02100"); strip before the 4-digit chart check.
    trimmed = digits.lstrip("0") or "0"
    if len(trimmed) < 4 or not trimmed.startswith("2"):
        return None
    try:
        number = int(trimmed[:4])
    except ValueError:
        return None
    if 2100 <= number <= 2299:
        return "CurrentLiabilities"
    if 2300 <= number <= 2999:
        return "LongTermLiabilities"
    return "CurrentLiabilities"


def _liability_bucket_for_line(line: dict[str, Any]) -> str | None:
    """Classify a parsed BS line; fall back to label when NominalCode is missing."""
    bucket = _liability_bucket_for_nominal(line.get("nominal_code"))
    if bucket:
        return bucket
    label = str(line.get("label") or "").strip().lower()
    if not label:
        return None
    if "creditors control" in label:
        return "CurrentLiabilities"
    # Default QuickFile chart: 2300 "Loans" / "Bank loan" are long-term.
    if label in {"loans", "loan", "bank loan", "bank loans"}:
        return "LongTermLiabilities"
    return None


def _section_lines_total(lines: list[dict[str, Any]]) -> float:
    return round(sum(abs(float(line.get("amount_gbp") or 0)) for line in lines), 2)


def _rehome_misfiled_liability_lines(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Move 2xxx liability nominals out of Current assets into liability sections."""
    by_key = {section["key"]: section for section in sections}
    current_assets = by_key.get("CurrentAssets")
    if not current_assets:
        return sections
    kept: list[dict[str, Any]] = []
    moved_current: list[dict[str, Any]] = []
    moved_long: list[dict[str, Any]] = []
    for line in current_assets.get("lines") or []:
        bucket = _liability_bucket_for_line(line)
        if bucket == "CurrentLiabilities":
            moved_current.append({**line, "amount_gbp": abs(float(line.get("amount_gbp") or 0))})
        elif bucket == "LongTermLiabilities":
            moved_long.append({**line, "amount_gbp": abs(float(line.get("amount_gbp") or 0))})
        else:
            kept.append(line)
    if not moved_current and not moved_long:
        return sections

    current_assets["lines"] = kept
    # Recalculate from remaining lines only when we actually moved liability nominals.
    current_assets["subtotal_gbp"] = round(
        sum(float(line.get("amount_gbp") or 0) for line in kept), 2
    )

    if moved_current:
        target = by_key.get("CurrentLiabilities")
        if target is not None:
            target["lines"] = list(target.get("lines") or []) + moved_current
            target["subtotal_gbp"] = _section_lines_total(target["lines"])
    if moved_long:
        target = by_key.get("LongTermLiabilities")
        if target is not None:
            target["lines"] = list(target.get("lines") or []) + moved_long
            target["subtotal_gbp"] = _section_lines_total(target["lines"])
    return sections


def _creditors_control_from_sections(sections: list[dict[str, Any]]) -> float:
    by_key = {section["key"]: section for section in sections}
    for key in ("CurrentLiabilities", "CurrentAssets"):
        section = by_key.get(key)
        if not section:
            continue
        for line in section.get("lines") or []:
            if _line_matches_label(str(line.get("label") or ""), "creditors control"):
                return round(abs(float(line.get("amount_gbp") or 0)), 2)
    return 0.0


def normalize_parsed_balance_sheet(bs: dict[str, Any]) -> dict[str, Any]:
    """Rehome misfiled 2xxx lines on an already-parsed balance sheet.

    Reports are stored as parsed JSON. Live refresh does not re-sync reports, so
    the read path must re-apply classification or stale Current assets keep 2100/2300.
    """
    sections = list(bs.get("sections") or [])
    if not sections:
        return bs
    current_assets = next((s for s in sections if s.get("key") == "CurrentAssets"), None)
    if not current_assets:
        return bs
    if not any(_liability_bucket_for_line(line) for line in (current_assets.get("lines") or [])):
        return bs

    sections = _rehome_misfiled_liability_lines(sections)
    by_key = {section["key"]: section for section in sections}
    current_assets = by_key.get("CurrentAssets")
    current_liabilities = by_key.get("CurrentLiabilities")
    long_term = by_key.get("LongTermLiabilities")
    if current_assets is not None and current_assets.get("subtotal_gbp") is not None:
        bs["current_assets_gbp"] = float(current_assets["subtotal_gbp"])
    if current_liabilities is not None and current_liabilities.get("subtotal_gbp") is not None:
        bs["current_liabilities_gbp"] = float(current_liabilities["subtotal_gbp"])
    if long_term is not None and long_term.get("subtotal_gbp") is not None:
        bs["long_term_liabilities_gbp"] = float(long_term["subtotal_gbp"])
    creditors = _creditors_control_from_sections(sections)
    if creditors > 0:
        bs["creditors_gbp"] = creditors
    bs["sections"] = sections
    return bs


def parse_profit_and_loss_full(
    body: dict[str, Any],
    *,
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    totals = body.get("Totals") or {}
    breakdown = body.get("Breakdown") or {}

    turnover = _float(totals.get("Turnover"))
    cost_of_sales = _abs_cost(_float(totals.get("LessCostofSales")))
    operating_expenses = _abs_cost(_float(totals.get("LessExpenses")))
    net_profit = _float(totals.get("NetProfit"))
    if net_profit == 0.0 and turnover:
        net_profit = round(turnover - cost_of_sales - operating_expenses, 2)
    gross_profit = round(turnover - cost_of_sales, 2)

    sections: list[dict[str, Any]] = []
    for key, label, total_key, use_abs in _PL_SECTIONS:
        section_body = breakdown.get(key)
        lines = _parse_section_lines(section_body, use_abs=use_abs)
        subtotal = _line_amount(_float(totals.get(total_key)), use_abs=use_abs)
        sections.append(
            {
                "key": key,
                "label": label,
                "lines": lines,
                "subtotal_gbp": subtotal,
            }
        )
        if key == "LessCostofSales":
            sections.append(
                {
                    "key": "GrossProfit",
                    "label": "Gross profit",
                    "lines": [],
                    "subtotal_gbp": gross_profit,
                    "subtotal_label": "Gross profit",
                }
            )

    sections.append(
        {
            "key": "NetProfit",
            "label": "Net profit",
            "lines": [],
            "subtotal_gbp": round(net_profit, 2),
            "subtotal_label": "Net profit",
            "is_total": True,
        }
    )

    return {
        "from_date": from_date,
        "to_date": to_date,
        "turnover_gbp": round(turnover, 2),
        "cost_of_sales_gbp": cost_of_sales,
        "expenses_gbp": round(cost_of_sales + operating_expenses, 2),
        "net_profit_gbp": round(net_profit, 2),
        "sections": sections,
    }


def parse_balance_sheet_full(body: dict[str, Any], *, to_date: str) -> dict[str, Any]:
    totals = body.get("Totals") or {}
    breakdown = body.get("Breakdown") or {}
    current_assets = breakdown.get("CurrentAssets") or {}
    current_liabilities = breakdown.get("CurrentLiabilities") or {}

    debtors = _line_amount_from_breakdown(current_assets, "debtors control")
    # Prefer liability section; some QuickFile charts misfile creditors under assets.
    creditors = _line_amount_from_breakdown(current_liabilities, "creditors control")
    if creditors <= 0:
        creditors = _line_amount_from_breakdown(current_assets, "creditors control")
    # Nominal 1210 "Vat Account" — cash reserved for VAT, not the creditor liability.
    vat_reserve = _line_amount_from_breakdown(current_assets, "vat account")
    vat_liability = _sum_lines_from_breakdown(
        current_liabilities, "vat liability", "sales tax control"
    )

    sections: list[dict[str, Any]] = []
    for index, (key, label, total_key, use_abs) in enumerate(_BS_SECTIONS):
        section_body = breakdown.get(key)
        lines = _parse_section_lines(section_body, use_abs=use_abs)
        subtotal = _line_amount(_float(totals.get(total_key)), use_abs=use_abs)
        sections.append(
            {
                "key": key,
                "label": label,
                "lines": lines,
                "subtotal_gbp": subtotal,
                "is_total": index == len(_BS_SECTIONS) - 1,
            }
        )
    parsed = {
        "to_date": to_date,
        "fixed_assets_gbp": round(_float(totals.get("FixedAssets")), 2),
        "current_assets_gbp": round(_float(totals.get("CurrentAssets")), 2),
        "current_liabilities_gbp": round(abs(_float(totals.get("CurrentLiabilities"))), 2),
        "long_term_liabilities_gbp": round(abs(_float(totals.get("LongTermLiabilities"))), 2),
        "capital_and_reserves_gbp": round(_float(totals.get("CapitalAndReserves")), 2),
        "debtors_gbp": debtors,
        "creditors_gbp": creditors,
        "vat_reserve_gbp": vat_reserve,
        "vat_liability_gbp": vat_liability,
        "sections": sections,
    }
    return normalize_parsed_balance_sheet(parsed)


def parse_profit_and_loss(
    body: dict[str, Any],
    *,
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    return parse_profit_and_loss_full(body, from_date=from_date, to_date=to_date)


def parse_balance_sheet(body: dict[str, Any], *, to_date: str) -> dict[str, Any]:
    return parse_balance_sheet_full(body, to_date=to_date)
