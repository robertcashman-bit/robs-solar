"""Previous deploys stored the Lunch Flow key as LUNCH_FLOW_API_KEY."""

from app.config import Settings
from app.services.lunchflow_settings_service import LunchFlowSettingsService


def test_settings_reads_legacy_lunch_flow_env_name(monkeypatch) -> None:
    monkeypatch.delenv("LUNCHFLOW_API_KEY", raising=False)
    monkeypatch.setenv("LUNCH_FLOW_API_KEY", "legacy-live-key")
    loaded = Settings(_env_file=None)
    assert loaded.lunchflow_api_key == "legacy-live-key"


def test_settings_prefers_current_lunchflow_name(monkeypatch) -> None:
    monkeypatch.setenv("LUNCHFLOW_API_KEY", "current-key")
    monkeypatch.setenv("LUNCH_FLOW_API_KEY", "legacy-live-key")
    loaded = Settings(_env_file=None)
    assert loaded.lunchflow_api_key == "current-key"


def test_lunchflow_settings_env_reads_legacy_name(monkeypatch) -> None:
    monkeypatch.setattr("app.services.lunchflow_settings_service.settings.lunchflow_api_key", "")
    monkeypatch.delenv("LUNCHFLOW_API_KEY", raising=False)
    monkeypatch.setenv("LUNCH_FLOW_API_KEY", "legacy-live-key")
    service = LunchFlowSettingsService()
    assert service.env_configured() is True
    assert service._env_config().api_key == "legacy-live-key"
