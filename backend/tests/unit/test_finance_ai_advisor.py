"""Unit tests for finance AI advisor."""

import json
from unittest.mock import AsyncMock

import pytest

from app.services.finance_ai_advisor_service import FinanceAiAdvisorService


@pytest.mark.asyncio
async def test_assess_uses_overview_context(monkeypatch) -> None:
    service = FinanceAiAdvisorService()
    captured: dict[str, object] = {}

    async def fake_context(db):  # noqa: ANN001
        return {
            "overview": {
                "personal_monthly_income_gbp": 5000,
                "business_income_from_quickfile": True,
                "business_monthly_turnover_gbp": 12000,
            }
        }

    async def fake_complete(messages):  # noqa: ANN001
        captured["messages"] = messages
        return json.dumps(
            {
                "summary": "Solid position.",
                "findings": [{"title": "QuickFile live", "detail": "Business income synced.", "severity": "info"}],
                "recommendations": ["Keep VAT reserve topped up."],
                "questions_you_might_ask": ["Can I afford to overpay the mortgage?"],
            }
        )

    monkeypatch.setattr(service, "build_context", fake_context)
    monkeypatch.setattr(service, "_complete", fake_complete)

    result = await service.assess(db=None)  # type: ignore[arg-type]
    assert result.summary == "Solid position."
    assert result.findings[0].title == "QuickFile live"
    assert "personal_monthly_income_gbp" in str(captured.get("messages"))
