"""Personal and business budget category registry. Users may add custom names."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AppSettingRow
from app.services.finance.budget_suggestion_service import (
    BUSINESS_CATEGORIES,
    PERSONAL_CATEGORIES,
)

_CUSTOM_KEY = "finance.custom_categories"
_RULES_KEY = "finance.category_rules"

# Extra labels used by the categoriser / DLS practice without changing budget suggestion cores.
_PERSONAL_EXTRA = [
    "Salary",
    "Dividends",
    "Director loan repayment",
    "Other income",
    "Mortgage / household contribution",
    "Council tax",
    "Restaurants",
    "Fuel",
    "Car",
    "Internet",
    "Shopping",
    "Entertainment",
    "Travel",
    "Professional costs",
    "Education support",
    "Cash withdrawals",
    "Credit card payments",
    "Loan repayments",
    "Interest",
    "Bank charges",
    "Tax",
    "Transfers",
]
_BUSINESS_EXTRA = [
    "Legal fee income",
    "Police station attendance income",
    "Duty solicitor income",
    "Mileage income",
    "Parking reimbursement",
    "Other business income",
    "Director payments",
    "Pension contributions",
    "Tesla / vehicle finance",
    "Vehicle expenses",
    "Professional indemnity",
    "Professional subscriptions",
    "Legal software",
    "IT/software",
    "Website/hosting",
    "Telephone/mobile",
    "Parking",
    "Bank charges",
    "Loan interest",
    "Credit card repayment",
    "Capital on Tap",
    "Funding Circle",
    "FlexiPay",
    "VAT",
    "Corporation tax",
    "Other tax",
    "Office costs",
    "Advertising/marketing",
    "Other business expense",
    "Transfers",
]

PERSONAL_REGISTRY = [
    {"parent": name, "subcategory": "", "scope": "personal"}
    for name in list(dict.fromkeys([*PERSONAL_CATEGORIES, *_PERSONAL_EXTRA]))
]
BUSINESS_REGISTRY = [
    {"parent": name, "subcategory": "", "scope": "business"}
    for name in list(dict.fromkeys([*BUSINESS_CATEGORIES, *_BUSINESS_EXTRA]))
]


async def list_categories(db: AsyncSession, scope: str | None = None) -> list[dict[str, str]]:
    seeded = list(PERSONAL_REGISTRY if scope != "business" else [])
    if scope != "personal":
        seeded.extend(BUSINESS_REGISTRY)
    if scope is None:
        seeded = list(PERSONAL_REGISTRY) + list(BUSINESS_REGISTRY)
    custom = await _load_json(db, _CUSTOM_KEY, [])
    for item in custom:
        if not isinstance(item, dict):
            continue
        item_scope = str(item.get("scope") or "")
        if scope and item_scope and item_scope != scope:
            continue
        seeded.append(
            {
                "parent": str(item.get("parent") or item.get("category") or "")[:64],
                "subcategory": str(item.get("subcategory") or "")[:64],
                "scope": item_scope or (scope or "personal"),
            }
        )
    return [item for item in seeded if item["parent"]]


async def add_custom_category(
    db: AsyncSession,
    *,
    scope: str,
    category: str,
    subcategory: str = "",
) -> list[dict[str, str]]:
    custom = await _load_json(db, _CUSTOM_KEY, [])
    entry = {
        "scope": scope,
        "parent": category[:64],
        "subcategory": subcategory[:64],
    }
    if entry not in custom:
        custom.append(entry)
        await _save_json(db, _CUSTOM_KEY, custom)
    return await list_categories(db, scope)


async def list_confirmed_rules(db: AsyncSession) -> list[dict[str, str]]:
    rules = await _load_json(db, _RULES_KEY, [])
    return [rule for rule in rules if isinstance(rule, dict) and rule.get("confirmed")]


async def confirm_rule(
    db: AsyncSession,
    *,
    pattern: str,
    category: str,
    scope: str,
    match_type: str = "CONTAINS",
    priority: int = 5,
) -> dict[str, str]:
    rules = await _load_json(db, _RULES_KEY, [])
    entry = {
        "pattern": pattern.strip().upper()[:80],
        "category": category[:64],
        "scope": scope,
        "match_type": (match_type or "CONTAINS").upper()[:16],
        "priority": int(priority),
        "confirmed": True,
    }
    existing = next(
        (
            item
            for item in rules
            if isinstance(item, dict)
            and str(item.get("pattern") or "").upper() == entry["pattern"]
            and item.get("scope") == scope
        ),
        None,
    )
    if existing:
        existing.update(entry)
    else:
        rules.append(entry)
    await _save_json(db, _RULES_KEY, rules)
    return entry


def apply_confirmed_rules(description: str, scope: str, rules: list[dict[str, str]]) -> str:
    text = (description or "").upper()
    for rule in rules:
        if rule.get("scope") and rule.get("scope") != scope:
            continue
        pattern = str(rule.get("pattern") or "").upper()
        if pattern and pattern in text:
            return str(rule.get("category") or "")
    return ""


async def _load_json(db: AsyncSession, key: str, default):
    row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == key))
    if row is None:
        return default
    try:
        data = json.loads(row.value)
    except json.JSONDecodeError:
        return default
    return data if isinstance(data, list) else default


async def _save_json(db: AsyncSession, key: str, value) -> None:
    payload = json.dumps(value)
    row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == key))
    if row is None:
        db.add(AppSettingRow(key=key, value=payload))
    else:
        row.value = payload
    await db.commit()
