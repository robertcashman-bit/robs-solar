"""Missing energy samples must not be treated as genuine zero generation."""

from types import SimpleNamespace

from app.schemas.domain import HistoryRange
from app.services.energy_activity import has_energy_activity, row_has_energy_activity


def test_all_zero_flows_are_not_activity() -> None:
    assert has_energy_activity() is False
    assert (
        has_energy_activity(solar_kwh=0.0, house_kwh=0.0, import_kwh=0.0, export_kwh=0.0)
        is False
    )


def test_night_import_is_activity() -> None:
    assert has_energy_activity(import_kwh=1.2, house_kwh=1.1) is True


def test_generation_only_is_activity() -> None:
    assert has_energy_activity(solar_kwh=8.4) is True


def test_daily_savings_row_without_flows_is_missing() -> None:
    row = SimpleNamespace(
        solar_kwh=0.0,
        house_kwh=0.0,
        import_kwh=0.0,
        export_kwh=0.0,
        estimated_saving_gbp=0.0,
    )
    assert row_has_energy_activity(row) is False


def test_energy_snapshot_row_uses_pv_kwh() -> None:
    row = SimpleNamespace(pv_kwh=12.2, house_kwh=0.0, import_kwh=0.4, export_kwh=8.1)
    assert row_has_energy_activity(row) is True


def test_history_range_day_still_exists() -> None:
    assert HistoryRange.DAY.value == "day"
