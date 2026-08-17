"""Apply categorisation rules to transaction descriptions."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.finance.category_registry import list_confirmed_rules

DEFAULT_RULES: list[dict[str, Any]] = []
for _scope, _pattern, _category, _priority in [
    ("business", "TESLA", "Vehicle finance", 10),
    ("business", "FUNDING CIRCLE", "Loan repayments", 10),
    ("business", "CAPITAL ON TAP", "Loan repayments", 10),
    ("business", "FLEXIPAY", "Loan repayments", 10),
    ("business", "HMRC", "VAT", 20),
    ("business", "VAT", "VAT", 30),
    ("business", "CORPORATION TAX", "Corporation tax", 10),
    ("business", "COMPANIES HOUSE", "Professional costs", 20),
    ("business", "SRA", "Professional subscriptions", 20),
    ("business", "LEXIS", "Legal software", 20),
    ("business", "WESTLAW", "Legal software", 20),
    ("business", "ACCOUNTAN", "Accountancy", 30),
    ("business", "PARKING", "Parking", 80),
    ("personal", "TESCO", "Food", 40),
    ("personal", "SAINSBURY", "Food", 40),
    ("personal", "ASDA", "Food", 40),
    ("personal", "NETFLIX", "Subscriptions", 20),
    ("personal", "SPOTIFY", "Subscriptions", 20),
    ("personal", "COUNCIL TAX", "Council tax", 10),
    ("personal", "BRITISH GAS", "Utilities", 20),
    ("personal", "OCTOPUS", "Utilities", 20),
    ("personal", "MORTGAGE", "Mortgage / household contribution", 10),
    ("personal", "TRANSFER", "Transfers", 90),
    ("business", "TRANSFER", "Transfers", 90),
    ("personal", "FASTER PAYMENT", "Transfers", 90),
]:
    DEFAULT_RULES.append(
        {
            "match_type": "CONTAINS",
            "pattern": _pattern,
            "category": _category,
            "scope": _scope,
            "priority": _priority,
        }
    )

TRANSFER_HINTS = (
    "TRANSFER",
    "TFR",
    "FASTER PAYMENT",
    "FPS",
    "BACS",
    "INTERNAL",
    "OWN ACCOUNT",
    "BETWEEN ACCOUNTS",
)


def _matches(match_type: str, pattern: str, text: str) -> bool:
    mt = (match_type or "CONTAINS").upper()
    pat = pattern or ""
    if not pat:
        return False
    if mt == "EXACT":
        return text == pat.upper()
    if mt == "STARTS_WITH":
        return text.startswith(pat.upper())
    if mt == "REGEX":
        try:
            return re.search(pat, text, flags=re.IGNORECASE) is not None
        except re.error:
            return False
    return pat.upper() in text


class FinanceCategoriserService:
    def looks_like_transfer(self, description: str) -> bool:
        text = (description or "").upper()
        return any(hint in text for hint in TRANSFER_HINTS)

    def categorise_description(
        self,
        description: str,
        *,
        scope: str,
        rules: list[dict[str, Any]] | None = None,
    ) -> dict[str, str]:
        text = (description or "").upper()
        combined = list(rules or []) + list(DEFAULT_RULES)
        combined.sort(key=lambda item: int(item.get("priority") or 100))
        for rule in combined:
            rule_scope = str(rule.get("scope") or "")
            if rule_scope and rule_scope != scope:
                continue
            pattern = str(rule.get("pattern") or rule.get("merchant") or "")
            match_type = str(rule.get("match_type") or rule.get("matchType") or "CONTAINS")
            if not _matches(match_type, pattern, text):
                continue
            category = str(rule.get("category") or "")
            confidence = "HIGH" if rule.get("confirmed") or match_type == "EXACT" else "MEDIUM"
            if match_type == "REGEX" and not rule.get("confirmed"):
                confidence = "LOW"
            return {
                "category": category,
                "confidence": confidence,
                "matched_pattern": pattern,
            }
        if self.looks_like_transfer(description):
            return {
                "category": "Transfers",
                "confidence": "MEDIUM",
                "matched_pattern": "transfer_hint",
            }
        return {"category": "", "confidence": "LOW", "matched_pattern": ""}

    async def categorise(
        self,
        db: AsyncSession,
        description: str,
        *,
        scope: str,
    ) -> dict[str, str]:
        confirmed = await list_confirmed_rules(db)
        rules = [
            {
                "match_type": "CONTAINS",
                "pattern": item.get("pattern"),
                "category": item.get("category"),
                "scope": item.get("scope"),
                "priority": 1,
                "confirmed": True,
            }
            for item in confirmed
        ]
        return self.categorise_description(description, scope=scope, rules=rules)


finance_categoriser_service = FinanceCategoriserService()
