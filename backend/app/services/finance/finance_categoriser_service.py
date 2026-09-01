"""Apply categorisation rules to transaction descriptions."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.finance.category_registry import list_confirmed_rules

DEFAULT_RULES: list[dict[str, Any]] = []
for _scope, _pattern, _category, _priority in [
    # Income first — payment-rail wording must not steal salary credits.
    ("personal", "SALARY", "Salary", 5),
    ("personal", "PAYROLL", "Salary", 5),
    ("personal", "WAGES", "Salary", 5),
    # Company payroll narratives often name the employer, not "SALARY".
    ("personal", "DEFENCE LEGAL", "Salary", 5),
    ("personal", "DEFENCELEGAL", "Salary", 5),
    ("personal", "DLS LTD", "Salary", 5),
    ("personal", "DIVIDEND", "Dividends", 10),
    ("personal", "DIRECTOR LOAN", "Director loan repayment", 15),
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
    # Strong own-account wording only — not FPS/BACS/FASTER PAYMENT alone.
    ("personal", "OWN ACCOUNT", "Transfers", 90),
    ("personal", "BETWEEN ACCOUNTS", "Transfers", 90),
    ("business", "OWN ACCOUNT", "Transfers", 90),
    ("business", "BETWEEN ACCOUNTS", "Transfers", 90),
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

# Clear own-account / internal-move language. Payment rails (FPS/BACS/Faster
# Payment) are *not* transfers by themselves — third-party salary credits use
# those rails and must stay as income unless an opposite-leg pair exists.
TRANSFER_HINTS = (
    "OWN ACCOUNT",
    "BETWEEN ACCOUNTS",
    "INTERNAL TRANSFER",
    "INTERNAL TFR",
    "TO MY ACCOUNT",
    "FROM MY ACCOUNT",
    "TO SAVINGS",
    "FROM SAVINGS",
    "TO CURRENT",
    "FROM CURRENT",
)

# Rails alone are ambiguous; used only to detect previously false-marked rows.
PAYMENT_RAIL_HINTS = (
    "FASTER PAYMENT",
    "FPS",
    "BACS",
)

SALARY_HINTS = (
    "SALARY",
    "PAYROLL",
    "WAGES",
    # Employer / company payroll narratives (BACS often omits "SALARY").
    "DEFENCE LEGAL",
    "DEFENCELEGAL",
    "DLS LTD",
)

# Cross-scope equal amounts are usually payroll or DLA, not "between my accounts".
# Only pair business↔personal when wording is clearly an internal move.
CROSS_SCOPE_TRANSFER_HINTS = (
    "OWN ACCOUNT",
    "BETWEEN ACCOUNTS",
    "INTERNAL TRANSFER",
    "INTERNAL TFR",
    "TO MY ACCOUNT",
    "FROM MY ACCOUNT",
    "DIRECTOR LOAN",
    "DIRECTORS LOAN",
    "DIRECTOR'S LOAN",
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
        """True only for clear own-account / internal-move wording."""
        text = (description or "").upper()
        if self.looks_like_salary(description):
            return False
        # Bare "TRANSFER" / "TFR" without own-account context is still a hint,
        # but payment rails alone are not.
        if any(hint in text for hint in TRANSFER_HINTS):
            return True
        if "TRANSFER" in text or re.search(r"\bTFR\b", text):
            # Avoid matching "TRANSFER" inside longer third-party narratives that
            # also look like salary/income.
            if self.looks_like_salary(description):
                return False
            return True
        return False

    def looks_like_salary(self, description: str) -> bool:
        text = (description or "").upper()
        return any(hint in text for hint in SALARY_HINTS)

    def looks_like_cross_scope_transfer(self, description: str) -> bool:
        """True only for clear own-account / director-loan wording across scopes.

        Equal business debit + personal credit without this wording is treated as
        payroll (or similar), not an internal transfer.
        """
        text = (description or "").upper()
        if self.looks_like_salary(description):
            return False
        if any(hint in text for hint in CROSS_SCOPE_TRANSFER_HINTS):
            return True
        if re.search(r"\bDLA\b", text):
            return True
        return False

    def looks_like_payment_rail_only(self, description: str) -> bool:
        """True when FPS/BACS/Faster Payment appear without own-account hints."""
        text = (description or "").upper()
        if not any(hint in text for hint in PAYMENT_RAIL_HINTS):
            return False
        return not self.looks_like_transfer(description)

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
