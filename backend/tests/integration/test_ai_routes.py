"""Integration tests for the AI assistant routes."""

import json

import pytest
from httpx import AsyncClient

from tests.conftest import login


@pytest.mark.asyncio
async def test_ai_status_disabled_by_default(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    response = await client.get("/ai/status")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["reason"]


@pytest.mark.asyncio
async def test_ai_assess_requires_admin(client: AsyncClient) -> None:
    await login(client, "viewer", "viewer-pass")
    response = await client.post("/ai/assess")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_ai_assess_returns_503_when_disabled(client: AsyncClient) -> None:
    await login(client, "admin", "admin-pass")
    response = await client.post("/ai/assess")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_ai_assess_works_when_enabled(client: AsyncClient, monkeypatch) -> None:
    from app.config import settings
    from app.services.ai_advisor_service import ai_advisor_service

    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    async def fake_complete(_messages):
        return json.dumps(
            {
                "optimal": True,
                "headline": "Settings look optimal.",
                "findings": ["Battery discharging to cover load."],
                "proposed_actions": [],
            }
        )

    monkeypatch.setattr(ai_advisor_service, "_complete", fake_complete)

    await login(client, "admin", "admin-pass")
    response = await client.post("/ai/assess")
    assert response.status_code == 200
    body = response.json()
    assert body["optimal"] is True
    assert body["headline"] == "Settings look optimal."


@pytest.mark.asyncio
async def test_ai_chat_works_when_enabled(client: AsyncClient, monkeypatch) -> None:
    from app.config import settings
    from app.services.ai_advisor_service import ai_advisor_service

    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    async def fake_complete(_messages):
        return json.dumps({"reply": "Your battery is fine.", "proposed_actions": []})

    monkeypatch.setattr(ai_advisor_service, "_complete", fake_complete)

    session = await login(client, "admin", "admin-pass")
    response = await client.post(
        "/ai/chat",
        json={"messages": [{"role": "user", "content": "Is my battery ok?"}]},
        headers={"X-CSRF-Token": session["csrf_token"]},
    )
    assert response.status_code == 200
    assert response.json()["reply"] == "Your battery is fine."
