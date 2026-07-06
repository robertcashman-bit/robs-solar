"""Read-only finance AI advisor."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.finance import (
    FinanceAiAssessment,
    FinanceAiChatMessage,
    FinanceAiChatResponse,
    FinanceAiFinding,
)
from app.services.finance.finance_cashflow_service import finance_cashflow_service
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service
from app.services.finance.quickfile_reports_service import quickfile_reports_service
from app.services.open_banking_settings_service import open_banking_settings_service

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the finance advisor for "Rob's Finance", a personal and business \
finance dashboard.

Rules:
- Personal and business finances are separate. Never mix VAT/corp tax reserves with personal spending.
- QuickFile P&L is the source of truth for business turnover, expenses, and profit when \
business_income_from_quickfile is true in context.
- Mortgage is long-term personal debt. Monthly household contribution to Sarah covers the mortgage — \
do not suggest double-counting mortgage as a separate direct debit in personal cashflow.
- Assets (property, pension, debtors, bank balances) are positive/credit. Debts (credit cards, loans, \
mortgage, director's loan) are amounts owed — show as negative impact on net worth.
- Fields listed in historic_fields are placeholders (marked H in UI) until Open Banking or manual updates \
replace them.
- You are READ-ONLY. Never suggest automating bank transfers or changing inverter settings.
- Be concise. Quote real numbers from context. Use GBP.

Respond ONLY with JSON matching the requested schema."""


class FinanceAiAdvisorService:
    def __init__(self) -> None:
        self._client: Any = None

    def status_reason(self) -> str:
        if not settings.ai_enabled:
            return "AI assistant is disabled (set AI_ENABLED=true)."
        if not settings.openai_api_key:
            return "No OpenAI API key configured (set OPENAI_API_KEY)."
        return ""

    @property
    def enabled(self) -> bool:
        return bool(settings.ai_enabled and settings.openai_api_key)

    async def _complete(self, messages: list[dict[str, str]]) -> str:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.ai_timeout_seconds,
            )
        response = await self._client.chat.completions.create(
            model=settings.ai_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return response.choices[0].message.content or "{}"

    async def build_context(self, db: AsyncSession) -> dict[str, Any]:
        ctx: dict[str, Any] = {}
        try:
            overview = await finance_overview_service.get_overview(db)
            ctx["overview"] = overview.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            ctx["overview_error"] = str(exc)

        try:
            personal = await finance_overview_service.latest_personal_snapshot(db)
            if personal:
                ctx["personal_snapshot"] = personal.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            ctx["personal_snapshot_error"] = str(exc)

        try:
            business = await finance_overview_service.latest_business_snapshot(db)
            if business:
                ctx["business_snapshot"] = business.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            ctx["business_snapshot_error"] = str(exc)

        try:
            reports = await quickfile_reports_service.get_stored_reports(db)
            if reports:
                ctx["quickfile_reports"] = reports.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            ctx["quickfile_reports_error"] = str(exc)

        try:
            liabilities = await finance_liabilities_service.list_liabilities(db)
            ctx["liabilities"] = [item.model_dump(mode="json") for item in liabilities]
        except Exception as exc:  # noqa: BLE001
            ctx["liabilities_error"] = str(exc)

        try:
            cashflow = await finance_cashflow_service.build_forecasts(db, horizon_days=30)
            ctx["cashflow_30d"] = cashflow.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            ctx["cashflow_error"] = str(exc)

        try:
            ob_status = await open_banking_settings_service.get_status(db)
            ctx["open_banking"] = ob_status.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001
            ctx["open_banking_error"] = str(exc)

        return ctx

    async def assess(self, db: AsyncSession) -> FinanceAiAssessment:
        context = await self.build_context(db)
        prompt = (
            f"{_SYSTEM_PROMPT}\n\n"
            'Return JSON: {"summary": str, "findings": [{"title": str, "detail": str, '
            '"severity": "info|warning|critical"}], "recommendations": [str], '
            '"questions_you_might_ask": [str]}\n\n'
            f"context:\n{json.dumps(context, default=str)}"
        )
        raw = await self._complete(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "Assess my current financial position."},
            ]
        )
        data = json.loads(raw)
        findings = [
            FinanceAiFinding.model_validate(item)
            for item in data.get("findings", [])
            if isinstance(item, dict)
        ]
        return FinanceAiAssessment(
            summary=str(data.get("summary") or "No summary returned."),
            findings=findings,
            recommendations=[str(x) for x in data.get("recommendations", []) if x],
            questions_you_might_ask=[
                str(x) for x in data.get("questions_you_might_ask", []) if x
            ],
        )

    async def chat(
        self, db: AsyncSession, messages: list[FinanceAiChatMessage]
    ) -> FinanceAiChatResponse:
        context = await self.build_context(db)
        history = [{"role": m.role, "content": m.content} for m in messages]
        prompt = (
            f"{_SYSTEM_PROMPT}\n\n"
            'Return JSON: {"reply": str}\n\n'
            f"context:\n{json.dumps(context, default=str)}"
        )
        raw = await self._complete(
            [{"role": "system", "content": prompt}, *history]
        )
        data = json.loads(raw)
        return FinanceAiChatResponse(reply=str(data.get("reply") or ""))


finance_ai_advisor_service = FinanceAiAdvisorService()
