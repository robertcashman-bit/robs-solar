"""Optimisation score (0-100) from daily performance metrics."""

from __future__ import annotations

from app.schemas.domain import (
    OptimisationScore,
    OptimisationScoreComponent,
    SavingsBreakdown,
    SystemWarning,
    SystemWarningSeverity,
)


def compute_optimisation_score(
    *,
    import_kwh: float,
    export_kwh: float,
    pv_kwh: float,
    self_consumption_pct: float,
    breakdown: SavingsBreakdown | None,
    warnings: list[SystemWarning],
) -> OptimisationScore:
    """Score breakdown: 25 + 20 + 20 + 15 + 10 + 10 = 100."""
    peak_import = breakdown.peak_import_kwh if breakdown else import_kwh
    cheap_import = breakdown.cheap_import_kwh if breakdown else 0.0
    battery_discharge = breakdown.battery_discharge_kwh if breakdown else 0.0
    peak_avoided = breakdown.peak_import_avoided_kwh if breakdown else 0.0

    if import_kwh <= 0:
        peak_pts = 25
    elif peak_import / max(import_kwh, 0.001) < 0.2:
        peak_pts = 25
    elif peak_import / max(import_kwh, 0.001) < 0.5:
        peak_pts = 15
    else:
        peak_pts = 5

    if battery_discharge >= 2.0 and peak_import < import_kwh * 0.3:
        discharge_pts = 20
    elif battery_discharge >= 0.5:
        discharge_pts = 12
    elif battery_discharge > 0:
        discharge_pts = 6
    else:
        discharge_pts = 0

    if cheap_import >= 1.0 and peak_import < import_kwh:
        cheap_pts = 20
    elif cheap_import > 0:
        cheap_pts = 12
    else:
        cheap_pts = 8 if import_kwh < 1 else 4

    if self_consumption_pct >= 80:
        self_pts = 15
    elif self_consumption_pct >= 50:
        self_pts = 10
    elif self_consumption_pct >= 25:
        self_pts = 5
    else:
        self_pts = 0

    export_ratio = export_kwh / max(pv_kwh, 0.001) if pv_kwh > 0 else 0
    if pv_kwh <= 0:
        export_pts = 10
    elif export_ratio < 0.3:
        export_pts = 10
    elif export_ratio < 0.6:
        export_pts = 6
    else:
        export_pts = 3

    red_count = sum(1 for w in warnings if w.severity == SystemWarningSeverity.RED)
    amber_count = sum(1 for w in warnings if w.severity == SystemWarningSeverity.AMBER)
    warn_pts = max(0, 10 - red_count * 4 - amber_count * 2)

    components = [
        OptimisationScoreComponent(
            label="Low peak-rate import",
            max_points=25,
            points=peak_pts,
            detail=f"{peak_import:.1f} kWh peak import of {import_kwh:.1f} kWh total",
        ),
        OptimisationScoreComponent(
            label="Battery discharge in expensive periods",
            max_points=20,
            points=discharge_pts,
            detail=f"{battery_discharge:.1f} kWh discharged, {peak_avoided:.1f} kWh peak avoided",
        ),
        OptimisationScoreComponent(
            label="Cheap overnight charging",
            max_points=20,
            points=cheap_pts,
            detail=f"{cheap_import:.1f} kWh off-peak import",
        ),
        OptimisationScoreComponent(
            label="Solar self-consumption",
            max_points=15,
            points=self_pts,
            detail=f"{self_consumption_pct:.0f}% of PV used on-site",
        ),
        OptimisationScoreComponent(
            label="Sensible export behaviour",
            max_points=10,
            points=export_pts,
            detail=f"{export_kwh:.1f} kWh exported of {pv_kwh:.1f} kWh generated",
        ),
        OptimisationScoreComponent(
            label="No system warnings",
            max_points=10,
            points=warn_pts,
            detail=f"{len(warnings)} warning(s) active",
        ),
    ]

    total = sum(c.points for c in components)
    lost: list[str] = []
    for c in components:
        if c.points < c.max_points:
            lost.append(
                f"You lost {c.max_points - c.points} points on {c.label.lower()}: {c.detail}"
            )

    missed = breakdown.peak_import_avoided_value if breakdown else 0.0

    return OptimisationScore(
        total=total,
        components=components,
        lost_points_reasons=lost,
        missed_saving_gbp=round(missed, 2),
    )
