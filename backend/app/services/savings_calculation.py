"""Transparent daily savings calculation with standing charge and breakdown."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.domain import SavingsBreakdown, SavingsBreakdownLine, TariffSettings


def _clamp_nonneg(value: float) -> float:
    if value != value:  # NaN
        return 0.0
    return max(0.0, value)


@dataclass
class SavingsInputs:
    consumption_kwh: float
    import_kwh: float
    export_kwh: float
    pv_kwh: float = 0.0
    cheap_import_kwh: float = 0.0
    peak_import_kwh: float = 0.0
    battery_charge_kwh: float = 0.0
    battery_discharge_kwh: float = 0.0
    peak_import_avoided_kwh: float = 0.0


@dataclass
class SavingsResult:
    import_cost: float
    export_credit: float
    standing_charge: float
    net_cost: float
    estimated_without_solar: float
    savings: float
    breakdown: SavingsBreakdown


def compute_savings(
    inputs: SavingsInputs,
    tariff: TariffSettings,
    *,
    import_rate_override: float | None = None,
    export_rate_override: float | None = None,
) -> SavingsResult:
    """Compute actual cost, no-solar cost, saving, and a transparent breakdown."""
    consumption = _clamp_nonneg(inputs.consumption_kwh)
    import_kwh = _clamp_nonneg(inputs.import_kwh)
    export_kwh = _clamp_nonneg(inputs.export_kwh)
    cheap_import = _clamp_nonneg(inputs.cheap_import_kwh)
    peak_import = _clamp_nonneg(inputs.peak_import_kwh)

    day_rate = import_rate_override if import_rate_override is not None else tariff.import_rate
    night_rate = tariff.night_import_rate if tariff.night_import_rate is not None else day_rate
    export_rate = export_rate_override if export_rate_override is not None else tariff.export_rate

    if cheap_import + peak_import > import_kwh + 0.001:
        # Normalise split if totals exceed import (sample/integration drift).
        total_split = cheap_import + peak_import
        scale = import_kwh / total_split if total_split > 0 else 1.0
        cheap_import *= scale
        peak_import *= scale
    elif cheap_import + peak_import < import_kwh - 0.001 and import_kwh > 0:
        # Assign remainder to peak when split unknown.
        peak_import = max(0.0, import_kwh - cheap_import)

    cheap_cost = cheap_import * night_rate
    peak_cost = peak_import * day_rate
    import_cost = (
        cheap_cost + peak_cost if cheap_import + peak_import > 0 else import_kwh * day_rate
    )
    export_credit = export_kwh * export_rate
    standing = tariff.standing_charge_gbp if tariff.include_standing_charge else 0.0
    net_cost = import_cost - export_credit + standing
    estimated_without_solar = consumption * day_rate + standing
    savings = estimated_without_solar - net_cost

    peak_avoided_kwh = _clamp_nonneg(inputs.peak_import_avoided_kwh)
    peak_avoided_value = peak_avoided_kwh * day_rate
    cheap_charging_cost = cheap_cost

    lines = [
        SavingsBreakdownLine(
            label="Grid import cost",
            amount=round(import_cost, 2),
            detail=f"{import_kwh:.2f} kWh imported"
            + (
                f" ({cheap_import:.2f} off-peak @ {night_rate:.4f}, "
                f"{peak_import:.2f} peak @ {day_rate:.4f})"
                if cheap_import + peak_import > 0
                else f" @ {day_rate:.4f}/kWh"
            ),
        ),
        SavingsBreakdownLine(
            label="Export credit",
            amount=round(-export_credit, 2),
            detail=f"{export_kwh:.2f} kWh exported @ {export_rate:.4f}/kWh",
        ),
    ]
    if standing > 0:
        lines.append(
            SavingsBreakdownLine(
                label="Standing charge",
                amount=round(standing, 2),
                detail="Daily standing charge included",
            )
        )
    lines.extend(
        [
            SavingsBreakdownLine(
                label="Actual daily cost",
                amount=round(net_cost, 2),
                detail="Import cost − export credit"
                + (" + standing charge" if standing > 0 else ""),
            ),
            SavingsBreakdownLine(
                label="Estimated cost without solar/battery",
                amount=round(estimated_without_solar, 2),
                detail=f"{consumption:.2f} kWh house use @ {day_rate:.4f}/kWh"
                + (" + standing charge" if standing > 0 else ""),
            ),
            SavingsBreakdownLine(
                label="Estimated saving",
                amount=round(savings, 2),
                detail="No-solar cost − actual cost",
            ),
        ]
    )

    breakdown = SavingsBreakdown(
        lines=lines,
        import_kwh=round(import_kwh, 3),
        export_kwh=round(export_kwh, 3),
        import_rate_gbp=day_rate,
        export_rate_gbp=export_rate,
        standing_charge_gbp=round(standing, 2),
        include_standing_charge=tariff.include_standing_charge,
        cheap_import_kwh=round(cheap_import, 3),
        peak_import_kwh=round(peak_import, 3),
        cheap_import_cost=round(cheap_cost, 2),
        peak_import_cost=round(peak_cost, 2),
        peak_import_avoided_kwh=round(peak_avoided_kwh, 3),
        peak_import_avoided_value=round(peak_avoided_value, 2),
        cheap_rate_charging_cost=round(cheap_charging_cost, 2),
        battery_charge_kwh=round(_clamp_nonneg(inputs.battery_charge_kwh), 3),
        battery_discharge_kwh=round(_clamp_nonneg(inputs.battery_discharge_kwh), 3),
    )

    return SavingsResult(
        import_cost=round(import_cost, 2),
        export_credit=round(export_credit, 2),
        standing_charge=round(standing, 2),
        net_cost=round(net_cost, 2),
        estimated_without_solar=round(estimated_without_solar, 2),
        savings=round(savings, 2),
        breakdown=breakdown,
    )
