"""Unit tests for shared effective load resolution."""

import pytest

from app.schemas.domain import HouseLoadSource
from app.services.effective_load import resolve_house_load


def test_resolve_house_load_prefers_derived_when_ct_underreports() -> None:
    watts, source = resolve_house_load(
        250,
        pv=0,
        grid_import=7200,
        grid_export=0,
        battery_power_w=0,
    )
    assert watts == pytest.approx(7200)
    assert source == HouseLoadSource.DERIVED


def test_resolve_house_load_trusts_reported_when_close_to_derived() -> None:
    watts, source = resolve_house_load(
        970,
        pv=30,
        grid_import=20,
        grid_export=0,
        battery_power_w=0,
    )
    assert watts == pytest.approx(970)
    assert source == HouseLoadSource.REPORTED
