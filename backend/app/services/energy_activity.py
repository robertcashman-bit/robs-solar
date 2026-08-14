"""Distinguish real energy activity from missing/unavailable samples."""

from __future__ import annotations

ACTIVITY_EPS = 0.0005


def has_energy_activity(
    *,
    solar_kwh: float = 0.0,
    house_kwh: float = 0.0,
    import_kwh: float = 0.0,
    export_kwh: float = 0.0,
) -> bool:
    """True when at least one energy flow was recorded.

    An all-zero day with no samples is missing data, not a genuine zero-generation
    night — night still has household consumption or grid import.
    """
    return any(
        abs(float(value or 0.0)) > ACTIVITY_EPS
        for value in (solar_kwh, house_kwh, import_kwh, export_kwh)
    )


def row_has_energy_activity(row: object) -> bool:
    solar = getattr(row, "solar_kwh", None)
    if solar is None:
        solar = getattr(row, "pv_kwh", 0.0)
    return has_energy_activity(
        solar_kwh=float(solar or 0.0),
        house_kwh=float(getattr(row, "house_kwh", 0.0) or 0.0),
        import_kwh=float(getattr(row, "import_kwh", 0.0) or 0.0),
        export_kwh=float(getattr(row, "export_kwh", 0.0) or 0.0),
    )
