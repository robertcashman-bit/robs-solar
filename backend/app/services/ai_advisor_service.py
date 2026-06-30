"""AI assistant for Rob's Solar.

Design goals / safety:
- The assistant is READ-ONLY. It never writes to the inverter directly. It can
  only *propose* changes; an admin confirms each one in the UI, which then calls
  the existing audited ``/controls/*`` endpoints (CSRF, rate limit, safety gate,
  read-back verification all still apply).
- The OpenAI API key lives only on the backend and is never returned to the UI.
- Every proposed action body is validated against the same Pydantic request
  model the control endpoint uses; invalid suggestions are dropped.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_adapter
from app.config import settings
from app.schemas.domain import (
    AI_ACTION_ENDPOINTS,
    AiActionKind,
    AiAssessment,
    AiChatMessage,
    AiChatResponse,
    AiProposedAction,
    AutoScheduleConfigRequest,
    ExportLimitRequest,
    HistoryRange,
    OperatingModeRequest,
    TouBandsRequest,
)
from app.services.analytics_service import analytics_service
from app.services.auto_schedule_service import auto_schedule_service
from app.services.octopus_client import octopus_client
from app.services.safety_settings_service import safety_settings_service
from app.services.sell_advisor_service import sell_advisor_service

logger = logging.getLogger(__name__)

_ACTION_MODELS = {
    AiActionKind.SET_TOU_BANDS.value: TouBandsRequest,
    AiActionKind.SET_EXPORT_LIMIT.value: ExportLimitRequest,
    AiActionKind.SET_OPERATING_MODE.value: OperatingModeRequest,
    AiActionKind.SET_AUTO_SCHEDULE.value: AutoScheduleConfigRequest,
}

_SYSTEM_PROMPT = """You are the energy optimisation assistant for "Rob's Solar", \
a home Sunsynk inverter + battery on the Octopus Intelligent Octopus Go (IOG) tariff.

Optimisation goal: minimise the electricity bill.
Rules of thumb for IOG:
- Grid-charge the battery to 100% ONLY during cheap windows (the IOG off-peak \
window plus any planned smart-charge dispatches). In those bands set \
target_soc_pct=100 and grid_charge_enabled=true.
- Outside cheap windows, never grid-charge. Set grid_charge_enabled=false and \
target_soc_pct to the configured SOC floor so the battery discharges to cover \
house load instead of importing from the grid.
- Importing from the grid at the expensive day rate while the battery is well \
above its SOC floor is a problem worth flagging.
- Use "rate_plan" in context for the user's own Octopus import tariff: \
cheap_rate_pence, peak_rate_pence, cheap_windows, peak_windows, current_is_cheap, \
and planned_cheap_windows. Never use wholesale Agile market prices — only \
rate_plan and tariff (the user's bill rates).
- The auto-scheduler already computes ideal bands ("computed_bands" in context). \
If the live bands match those, the schedule is optimal.
- Selling to the grid: when the export rate is high (see "sell_opportunity" in \
context) and the battery has headroom above its reserve, it can be worth \
exporting. To start selling, propose set_operating_mode with mode "feed_in" \
(selling). To stop, propose mode "self_use". Only recommend selling energy the \
home will not need to cover the expensive evening peak.

You will receive a JSON "context" describing the live system. Respond ONLY with \
JSON matching the requested schema. Be concise and specific. Quote real numbers \
from the context. Only propose an action when it concretely improves cost or \
safety; otherwise return an empty proposed_actions list.

Allowed proposed action kinds and their body shapes:
- "set_tou_bands": {"bands": [{"slot": 1-6, "start": "HH:MM", \
"target_soc_pct": 0-100, "grid_charge_enabled": bool, "power_w": int}]}
- "set_export_limit": {"limit_w": int multiple of 100, 0-8000}
- "set_operating_mode": {"mode": "self_use|backup|feed_in|off_grid"}
- "set_auto_schedule": {"enabled": bool, "soc_floor_pct": 0-100}
"""


class AiAdvisorService:
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
        """Call OpenAI and return the raw JSON string. Isolated so tests can
        monkeypatch it without network access."""
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
        """Collect a read-only snapshot of the system. Each block is defensive so
        one failing integration does not break the whole assistant."""
        ctx: dict[str, Any] = {
            "iog_offpeak_window": {
                "start": settings.iog_offpeak_start,
                "end": settings.iog_offpeak_end,
            },
            "auto_schedule_soc_floor_default_pct": settings.auto_schedule_soc_floor_pct,
        }
        adapter = get_adapter()

        try:
            live = await adapter.get_live_metrics()
            ctx["live_metrics"] = {
                "pv_power_w": live.pv_power_w,
                "battery_soc_pct": live.battery_soc_pct,
                "battery_power_w": live.battery_power_w,
                "house_load_w": live.house_load_w,
                "grid_import_w": live.grid_import_w,
                "grid_export_w": live.grid_export_w,
                "inverter_mode": live.inverter_mode.value,
                "inverter_status": live.inverter_status.value,
            }
        except Exception as exc:  # noqa: BLE001 - context is best-effort
            ctx["live_metrics_error"] = str(exc)

        try:
            inv = await adapter.get_inverter_settings()
            if inv is not None:
                ctx["inverter_settings"] = {
                    "write_allowed": inv.write_allowed,
                    "sys_work_mode_label": inv.sys_work_mode_label,
                    "solar_sell": inv.solar_sell,
                    "active_band_slot": inv.active_band_slot,
                    "diagnosis": inv.diagnosis,
                    "bands": [
                        {
                            "slot": b.slot,
                            "start": b.start,
                            "end": b.end,
                            "target_soc_pct": b.target_soc_pct,
                            "grid_charge_enabled": b.grid_charge_enabled,
                            "power_w": b.power_w,
                        }
                        for b in inv.bands
                    ],
                }
        except Exception as exc:  # noqa: BLE001
            ctx["inverter_settings_error"] = str(exc)

        try:
            auto = await auto_schedule_service.get_status(db)
            ctx["auto_schedule"] = {
                "enabled": auto.enabled,
                "soc_floor_pct": auto.soc_floor_pct,
                "last_run_message": auto.last_run_message,
                "computed_bands": [
                    {
                        "slot": b.slot,
                        "start": b.start,
                        "target_soc_pct": b.target_soc_pct,
                        "grid_charge_enabled": b.grid_charge_enabled,
                        "power_w": b.power_w,
                    }
                    for b in auto.computed_bands
                ],
                "next_cheap_windows": [
                    {"start": w.start.isoformat(), "end": w.end.isoformat()}
                    for w in auto.next_cheap_windows
                ],
            }
        except Exception as exc:  # noqa: BLE001
            ctx["auto_schedule_error"] = str(exc)

        try:
            if octopus_client.configured():
                import_rate = await octopus_client.get_import_rate_gbp()
                export_rate = await octopus_client.get_export_rate_gbp()
                ctx["tariff"] = {
                    "import_rate_gbp_per_kwh": import_rate,
                    "export_rate_gbp_per_kwh": export_rate,
                }
                plan = await octopus_client.get_rate_plan()
                if plan.configured:
                    ctx["rate_plan"] = {
                        "tariff_family": plan.tariff_family,
                        "import_display_name": plan.import_display_name,
                        "region": plan.region,
                        "cheap_rate_pence": plan.cheap_rate_pence,
                        "peak_rate_pence": plan.peak_rate_pence,
                        "cheap_windows": [
                            {"start": w.start, "end": w.end} for w in plan.cheap_windows
                        ],
                        "peak_windows": [
                            {"start": w.start, "end": w.end} for w in plan.peak_windows
                        ],
                        "current_rate_pence": plan.current_rate_pence,
                        "current_is_cheap": plan.current_is_cheap,
                        "planned_cheap_windows": [
                            {
                                "start": w.start,
                                "end": w.end,
                                "source": w.source,
                            }
                            for w in plan.planned_cheap_windows
                        ],
                    }
        except Exception as exc:  # noqa: BLE001
            ctx["tariff_error"] = str(exc)

        try:
            opportunity = await sell_advisor_service.get_opportunity(adapter)
            ctx["sell_opportunity"] = {
                "worth_selling": opportunity.worth_selling,
                "export_rate_pence": opportunity.export_rate_pence,
                "threshold_pence": opportunity.threshold_pence,
                "sellable_kwh": opportunity.sellable_kwh,
                "estimated_value_gbp": opportunity.estimated_value_gbp,
                "headline": opportunity.headline,
            }
        except Exception as exc:  # noqa: BLE001
            ctx["sell_opportunity_error"] = str(exc)

        try:
            summary = await analytics_service.get_summary(db, HistoryRange.DAY)
            ctx["today_summary"] = {
                "pv_kwh": summary.pv_kwh,
                "import_kwh": summary.import_kwh,
                "export_kwh": summary.export_kwh,
                "net_cost": summary.net_cost,
                "savings": summary.savings,
                "currency": summary.currency,
            }
        except Exception as exc:  # noqa: BLE001
            ctx["today_summary_error"] = str(exc)

        try:
            safety = await safety_settings_service.get_settings(db)
            ctx["safety"] = {
                "read_only": safety.read_only,
                "enable_live_writes": safety.enable_live_writes,
            }
        except Exception as exc:  # noqa: BLE001
            ctx["safety_error"] = str(exc)

        return ctx

    def _normalise_actions(self, raw_actions: Any) -> list[AiProposedAction]:
        actions: list[AiProposedAction] = []
        if not isinstance(raw_actions, list):
            return actions
        for raw in raw_actions:
            if not isinstance(raw, dict):
                continue
            kind = raw.get("kind")
            model = _ACTION_MODELS.get(kind)
            if model is None:
                continue
            body = raw.get("body") or {}
            try:
                validated = model.model_validate(body)
            except Exception:  # noqa: BLE001 - drop invalid suggestions
                logger.info("Dropping invalid AI action of kind %s", kind)
                continue
            actions.append(
                AiProposedAction(
                    kind=AiActionKind(kind),
                    endpoint=AI_ACTION_ENDPOINTS[kind],
                    summary=str(raw.get("summary") or ""),
                    reason=str(raw.get("reason") or ""),
                    body=validated.model_dump(mode="json"),
                )
            )
        return actions

    async def assess(self, db: AsyncSession) -> AiAssessment:
        context = await self.build_context(db)
        user_prompt = (
            "Assess whether the current solar/battery settings are optimal right "
            "now. Respond with JSON of shape: {\"optimal\": bool, \"headline\": "
            "str, \"findings\": [str], \"proposed_actions\": [{\"kind\": str, "
            "\"summary\": str, \"reason\": str, \"body\": object}]}.\n\n"
            f"context = {json.dumps(context, default=str)}"
        )
        raw = await self._complete(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )
        data = _safe_json(raw)
        return AiAssessment(
            optimal=bool(data.get("optimal", False)),
            headline=str(data.get("headline") or "Assessment complete."),
            findings=[str(f) for f in (data.get("findings") or []) if str(f).strip()],
            proposed_actions=self._normalise_actions(data.get("proposed_actions")),
        )

    async def chat(self, db: AsyncSession, history: list[AiChatMessage]) -> AiChatResponse:
        context = await self.build_context(db)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "system",
                "content": (
                    "Answer the user's question. Respond with JSON of shape: "
                    '{"reply": str, "proposed_actions": [{"kind": str, "summary": '
                    'str, "reason": str, "body": object}]}. Use proposed_actions '
                    "only if the user asks you to change something or a change is "
                    f"clearly beneficial.\n\ncontext = {json.dumps(context, default=str)}"
                ),
            },
        ]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        raw = await self._complete(messages)
        data = _safe_json(raw)
        return AiChatResponse(
            reply=str(data.get("reply") or "Sorry, I could not produce an answer."),
            proposed_actions=self._normalise_actions(data.get("proposed_actions")),
        )


def _safe_json(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


ai_advisor_service = AiAdvisorService()
