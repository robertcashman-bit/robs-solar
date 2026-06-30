"""Unit tests for the AI advisor service (no network — _complete is mocked)."""

import json

import pytest

from app.schemas.domain import AiActionKind
from app.services.ai_advisor_service import AiAdvisorService


def test_normalise_actions_keeps_valid_and_drops_invalid() -> None:
    service = AiAdvisorService()
    raw = [
        {
            "kind": "set_export_limit",
            "summary": "Cap export",
            "reason": "avoid clipping",
            "body": {"limit_w": 3600},
        },
        {
            "kind": "set_export_limit",
            "summary": "bad",
            "reason": "bad",
            "body": {"limit_w": 3650},  # not a multiple of 100 -> invalid
        },
        {"kind": "not_a_real_kind", "body": {}},
    ]
    actions = service._normalise_actions(raw)
    assert len(actions) == 1
    assert actions[0].kind == AiActionKind.SET_EXPORT_LIMIT
    assert actions[0].endpoint == "/controls/export-limit"
    assert actions[0].body["limit_w"] == 3600


def test_normalise_actions_validates_tou_bands() -> None:
    service = AiAdvisorService()
    raw = [
        {
            "kind": "set_tou_bands",
            "summary": "discharge in day",
            "reason": "battery above floor",
            "body": {
                "bands": [
                    {
                        "slot": 1,
                        "start": "00:00",
                        "target_soc_pct": 100,
                        "grid_charge_enabled": True,
                        "power_w": 8000,
                    },
                    {
                        "slot": 2,
                        "start": "05:30",
                        "target_soc_pct": 20,
                        "grid_charge_enabled": False,
                        "power_w": 8000,
                    },
                ]
            },
        }
    ]
    actions = service._normalise_actions(raw)
    assert len(actions) == 1
    assert actions[0].endpoint == "/controls/tou"
    assert len(actions[0].body["bands"]) == 2


@pytest.mark.asyncio
async def test_assess_parses_completion(monkeypatch) -> None:
    service = AiAdvisorService()

    async def fake_build_context(_db):
        return {"stub": True}

    async def fake_complete(_messages):
        return json.dumps(
            {
                "optimal": False,
                "headline": "Grid importing while battery at 96%.",
                "findings": ["Battery well above floor but grid import 39W."],
                "proposed_actions": [
                    {
                        "kind": "set_auto_schedule",
                        "summary": "Enable auto-align",
                        "reason": "Keeps bands aligned to cheap windows.",
                        "body": {"enabled": True, "soc_floor_pct": 20},
                    }
                ],
            }
        )

    monkeypatch.setattr(service, "build_context", fake_build_context)
    monkeypatch.setattr(service, "_complete", fake_complete)

    assessment = await service.assess(db=None)  # type: ignore[arg-type]
    assert assessment.optimal is False
    assert "96%" in assessment.headline
    assert len(assessment.proposed_actions) == 1
    assert assessment.proposed_actions[0].kind == AiActionKind.SET_AUTO_SCHEDULE


@pytest.mark.asyncio
async def test_chat_handles_garbage_json(monkeypatch) -> None:
    service = AiAdvisorService()

    async def fake_build_context(_db):
        return {}

    async def fake_complete(_messages):
        return "not json at all"

    monkeypatch.setattr(service, "build_context", fake_build_context)
    monkeypatch.setattr(service, "_complete", fake_complete)

    from app.schemas.domain import AiChatMessage

    resp = await service.chat(db=None, history=[AiChatMessage(role="user", content="hi")])  # type: ignore[arg-type]
    assert resp.reply
    assert resp.proposed_actions == []


@pytest.mark.asyncio
async def test_build_context_includes_rate_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.schemas.domain import OctopusRatePlan, RatePlanWindow
    from app.services.ai_advisor_service import ai_advisor_service

    def fake_configured() -> bool:
        return True

    async def fake_import_rate() -> float:
        return 0.286

    async def fake_export_rate() -> float:
        return 0.12

    async def fake_rate_plan() -> OctopusRatePlan:
        return OctopusRatePlan(
            configured=True,
            tariff_family="IOG",
            region="J",
            import_display_name="Intelligent Octopus Go",
            cheap_rate_pence=7.0,
            peak_rate_pence=28.6,
            cheap_windows=[RatePlanWindow(start="23:30", end="05:30")],
            peak_windows=[RatePlanWindow(start="05:30", end="23:30")],
            current_rate_pence=28.6,
            current_is_cheap=False,
        )

    monkeypatch.setattr(
        "app.services.ai_advisor_service.octopus_client.configured",
        fake_configured,
    )
    monkeypatch.setattr(
        "app.services.ai_advisor_service.octopus_client.get_import_rate_gbp",
        fake_import_rate,
    )
    monkeypatch.setattr(
        "app.services.ai_advisor_service.octopus_client.get_export_rate_gbp",
        fake_export_rate,
    )
    monkeypatch.setattr(
        "app.services.ai_advisor_service.octopus_client.get_rate_plan",
        fake_rate_plan,
    )

    ctx = await ai_advisor_service.build_context(db=None)  # type: ignore[arg-type]
    assert ctx["tariff"]["import_rate_gbp_per_kwh"] == 0.286
    assert ctx["rate_plan"]["tariff_family"] == "IOG"
    assert ctx["rate_plan"]["cheap_rate_pence"] == 7.0
    assert ctx["rate_plan"]["peak_rate_pence"] == 28.6
    assert ctx["rate_plan"]["current_is_cheap"] is False
    assert ctx["rate_plan"]["cheap_windows"][0]["start"] == "23:30"
