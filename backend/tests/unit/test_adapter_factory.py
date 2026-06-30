"""Tests for the adapter factory's instance caching."""

import pytest

import app.adapters.factory as factory
from app.adapters.factory import get_adapter
from app.adapters.simulator import SimulatorAdapter
from app.adapters.sunsynk_connect import SunsynkConnectAdapter
from app.config import settings


def test_sunsynk_adapter_is_cached_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "adapter_mode", "sunsynk_connect")
    monkeypatch.setattr(factory, "_sunsynk_adapter", None)
    first = get_adapter()
    second = get_adapter()
    assert isinstance(first, SunsynkConnectAdapter)
    # Sharing one instance keeps a single Sunsynk auth token across all callers.
    assert first is second


def test_simulator_adapter_is_not_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "adapter_mode", "simulator")
    first = get_adapter()
    second = get_adapter()
    assert isinstance(first, SimulatorAdapter)
    assert first is not second
