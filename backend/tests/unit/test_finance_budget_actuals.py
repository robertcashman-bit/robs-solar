"""Blank budget actuals stay missing instead of counting as £0 spend."""

from types import SimpleNamespace

from app.services.finance.finance_budget_service import recorded_actual_gbp


def test_starter_and_plan_seed_actuals_are_unrecorded() -> None:
    assert recorded_actual_gbp(SimpleNamespace(actual_gbp=0.0, notes="Starter category")) is None
    assert recorded_actual_gbp(SimpleNamespace(actual_gbp=0.0, notes="From active budget")) is None
    assert recorded_actual_gbp(SimpleNamespace(actual_gbp=0.0, notes="Unrecorded actual")) is None


def test_explicit_zero_actual_is_recorded() -> None:
    assert recorded_actual_gbp(SimpleNamespace(actual_gbp=0.0, notes="")) == 0.0


def test_recorded_positive_actual_is_kept() -> None:
    assert recorded_actual_gbp(SimpleNamespace(actual_gbp=45.5, notes="Starter category")) == 45.5
