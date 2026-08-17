"""Optional AI commentary on pre-computed finance metrics only.

Never sends raw bank transactions. Requires settings.ai_enabled and an API key.
Labels every claim as FACT / CALCULATION / ESTIMATE / SUGGESTION.
"""

from __future__ import annotations

from typing import Any

from app.config import settings


class FinanceAiInsightsService:
    def enabled(self) -> bool:
        return bool(getattr(settings, "ai_enabled", False) and settings.openai_api_key)

    def status_reason(self) -> str:
        if not getattr(settings, "ai_enabled", False):
            return "AI insights are disabled. Enable AI in settings to interpret metrics only."
        if not settings.openai_api_key:
            return "OpenAI API key is not configured."
        return ""

    async def interpret_metrics(self, metrics: dict[str, Any], prompt: str) -> dict[str, Any]:
        if not self.enabled():
            return {
                "enabled": False,
                "reason": self.status_reason(),
                "labels": ["FACT", "CALCULATION", "ESTIMATE", "SUGGESTION"],
                "message": (
                    "Core budgeting works without AI. Enable AI explicitly to interpret "
                    "summary metrics — transaction rows are never sent."
                ),
            }
        # Deterministic local interpretation when AI is enabled but we still avoid
        # inventing arithmetic — only narrate supplied metrics.
        safe = metrics.get("safe_to_spend") or {}
        lines = [
            "FACT: Figures below were calculated by the finance engine, not by the model.",
            (
                "CALCULATION: Personal safe-to-spend = "
                f"{safe.get('personal', {}).get('safe_to_spend_gbp', 'n/a')}."
            ),
            (
                "CALCULATION: Business available cash = "
                f"{safe.get('business', {}).get('available_business_cash_gbp', 'n/a')}."
            ),
            f"ESTIMATE: Cash status = {metrics.get('cash_status', 'unknown')}.",
            (
                f"SUGGESTION: Prompt was “{prompt}”. "
                "Review Budget and Cash Flow for the underlying maths."
            ),
        ]
        return {
            "enabled": True,
            "labels": ["FACT", "CALCULATION", "ESTIMATE", "SUGGESTION"],
            "metrics_used": list(metrics.keys()),
            "analysis": "\n".join(lines),
            "disclaimer": "AI does not replace accountant advice or authoritative arithmetic.",
        }


finance_ai_insights_service = FinanceAiInsightsService()
