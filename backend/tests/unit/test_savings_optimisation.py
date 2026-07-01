"""Unit tests for savings calculation and optimisation scoring."""

from app.schemas.domain import SystemWarning, SystemWarningSeverity, TariffSettings
from app.services.optimisation_score_service import compute_optimisation_score
from app.services.savings_calculation import SavingsInputs, compute_savings


def test_actual_cost_import_only() -> None:
    tariff = TariffSettings(import_rate=0.25, export_rate=0.12, currency="GBP")
    result = compute_savings(
        SavingsInputs(consumption_kwh=10, import_kwh=4, export_kwh=0),
        tariff,
    )
    assert result.import_cost == 1.0
    assert result.export_credit == 0.0
    assert result.net_cost == 1.0


def test_actual_cost_with_export_credit() -> None:
    tariff = TariffSettings(import_rate=0.25, export_rate=0.12, currency="GBP")
    result = compute_savings(
        SavingsInputs(consumption_kwh=10, import_kwh=4, export_kwh=2),
        tariff,
    )
    assert result.net_cost == 0.76
    assert result.savings == round(10 * 0.25 - 0.76, 2)


def test_standing_charge_included() -> None:
    tariff = TariffSettings(
        import_rate=0.25,
        export_rate=0.12,
        currency="GBP",
        standing_charge_gbp=0.5,
        include_standing_charge=True,
    )
    result = compute_savings(
        SavingsInputs(consumption_kwh=10, import_kwh=2, export_kwh=0),
        tariff,
    )
    assert result.standing_charge == 0.5
    assert result.net_cost == 1.0


def test_standing_charge_excluded() -> None:
    tariff = TariffSettings(
        import_rate=0.25,
        export_rate=0.12,
        currency="GBP",
        standing_charge_gbp=0.5,
        include_standing_charge=False,
    )
    result = compute_savings(
        SavingsInputs(consumption_kwh=10, import_kwh=2, export_kwh=0),
        tariff,
    )
    assert result.standing_charge == 0.0


def test_negative_readings_clamped() -> None:
    tariff = TariffSettings(import_rate=0.25, export_rate=0.12, currency="GBP")
    result = compute_savings(
        SavingsInputs(consumption_kwh=-1, import_kwh=-2, export_kwh=-1),
        tariff,
    )
    assert result.import_cost == 0.0
    assert result.net_cost == 0.0


def test_optimisation_score_no_warnings() -> None:
    score = compute_optimisation_score(
        import_kwh=1,
        export_kwh=0.5,
        pv_kwh=5,
        self_consumption_pct=80,
        breakdown=None,
        warnings=[],
    )
    assert 0 <= score.total <= 100


def test_optimisation_score_loses_points_with_red_warning() -> None:
    score = compute_optimisation_score(
        import_kwh=5,
        export_kwh=0,
        pv_kwh=2,
        self_consumption_pct=20,
        breakdown=None,
        warnings=[
            SystemWarning(
                id="battery_not_discharging",
                severity=SystemWarningSeverity.RED,
                title="Battery may not be discharging",
                message="test",
                category="battery",
            )
        ],
    )
    assert score.total < 100
    assert len(score.lost_points_reasons) > 0
