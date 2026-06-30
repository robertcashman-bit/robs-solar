"""Unit tests for Octopus rate plan derivation."""

from datetime import datetime, timedelta, timezone

from app.services.octopus_rate_plan import derive_rate_plan


def test_two_tier_iog_uses_offpeak_windows_when_few_slots() -> None:
    rates = [
        {
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2027-01-01T00:00:00Z",
            "value_inc_vat": 7.0,
        },
        {
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2027-01-01T00:00:00Z",
            "value_inc_vat": 28.6,
        },
    ]
    plan = derive_rate_plan(
        rates,
        tariff_family="IOG",
        region="J",
        import_display_name="Intelligent Octopus Go",
        standing_charge_pence=45.0,
        offpeak_start="23:30",
        offpeak_end="05:30",
        planned=[],
        now=datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
    )
    assert plan.configured is True
    assert plan.cheap_rate_pence == 7.0
    assert plan.peak_rate_pence == 28.6
    assert len(plan.cheap_windows) == 1
    assert plan.cheap_windows[0].start == "23:30"
    assert plan.current_is_cheap is False


def test_flat_tariff_single_tier() -> None:
    rates = [
        {
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2027-01-01T00:00:00Z",
            "value_inc_vat": 24.5,
        },
    ]
    plan = derive_rate_plan(
        rates,
        tariff_family="FIXED",
        region="J",
        import_display_name="Fixed",
        standing_charge_pence=50.0,
        offpeak_start="23:30",
        offpeak_end="05:30",
        planned=[],
    )
    assert plan.cheap_rate_pence == 24.5
    assert plan.peak_rate_pence == 24.5
    assert plan.cheap_windows == []


def test_half_hourly_slots_build_cheap_windows() -> None:
    rates = []
    for hour in range(24):
        for half in (0, 30):
            start = datetime(2026, 6, 30, hour, half, tzinfo=timezone.utc)
            if half == 0:
                end = start + timedelta(minutes=30)
            else:
                end = start + timedelta(minutes=30)
            cheap = hour >= 23 or hour < 5 or (hour == 5 and half == 0)
            rates.append(
                {
                    "valid_from": start.isoformat().replace("+00:00", "Z"),
                    "valid_to": end.isoformat().replace("+00:00", "Z"),
                    "value_inc_vat": 7.0 if cheap else 28.0,
                }
            )
    plan = derive_rate_plan(
        rates,
        tariff_family="IOG",
        region="J",
        import_display_name="IOG",
        standing_charge_pence=None,
        offpeak_start="23:30",
        offpeak_end="05:30",
        planned=[],
        now=datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
    )
    assert plan.cheap_rate_pence == 7.0
    assert plan.peak_rate_pence == 28.0
    assert len(plan.cheap_windows) >= 1
