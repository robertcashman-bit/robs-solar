"""Tests for the adapter factory."""

import pytest

from app.adapters.factory import get_adapter, get_sunsynk_adapter
from app.adapters.simulator import SimulatorAdapter
from app.config import settings


def test_sunsynk_mode_uses_simulator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "adapter_mode", "sunsynk_connect")
    adapter = get_adapter()
    assert isinstance(adapter, SimulatorAdapter)


def test_simulator_adapter_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "adapter_mode", "simulator")
    first = get_adapter()
    second = get_adapter()
    assert isinstance(first, SimulatorAdapter)
    assert first is not second


def test_get_sunsynk_adapter_is_inert_when_energy_is_off() -> None:
    assert get_sunsynk_adapter() is None
