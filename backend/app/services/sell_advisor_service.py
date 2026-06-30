"""Advise when it is worth selling (exporting) stored energy to the grid."""

from __future__ import annotations

from app.adapters.base import InverterAdapter
from app.config import settings
from app.schemas.domain import SellOpportunity
from app.services.octopus_client import octopus_client


def evaluate_sell_opportunity(
    *,
    battery_soc_pct: float,
    export_rate_gbp: float | None,
    import_rate_gbp: float | None,
    threshold_gbp: float,
    min_soc_pct: int,
    capacity_kwh: float,
    configured: bool,
) -> SellOpportunity:
    """Pure decision logic for the sell-to-grid advisor."""
    export_pence = round(export_rate_gbp * 100, 1) if export_rate_gbp is not None else None
    import_pence = round(import_rate_gbp * 100, 1) if import_rate_gbp is not None else None
    threshold_pence = round(threshold_gbp * 100, 1)

    headroom_pct = max(0.0, battery_soc_pct - min_soc_pct)
    sellable_kwh = round(headroom_pct / 100.0 * capacity_kwh, 2)

    if not configured or export_rate_gbp is None:
        return SellOpportunity(
            worth_selling=False,
            battery_soc_pct=battery_soc_pct,
            export_rate_pence=export_pence,
            import_rate_pence=import_pence,
            threshold_pence=threshold_pence,
            sellable_kwh=sellable_kwh,
            estimated_value_gbp=0.0,
            headline="Export pricing unavailable",
            message=(
                "Connect Octopus to see live export prices and sell-to-grid advice."
                if not configured
                else "No live export rate available right now."
            ),
            configured=configured,
        )

    rate_ok = export_rate_gbp >= threshold_gbp
    soc_ok = battery_soc_pct > min_soc_pct and sellable_kwh > 0
    worth_selling = rate_ok and soc_ok
    estimated_value = round(sellable_kwh * export_rate_gbp, 2)

    if worth_selling:
        headline = f"Worth selling now at {export_pence:.1f}p/kWh"
        message = (
            f"Export is paying {export_pence:.1f}p/kWh (threshold {threshold_pence:.1f}p). "
            f"You can sell about {sellable_kwh:.1f} kWh above your {min_soc_pct}% reserve, "
            f"worth roughly £{estimated_value:.2f}. Switch to Feed-in (selling) mode to export."
        )
    elif rate_ok and not soc_ok:
        headline = "Good export price, but battery near reserve"
        message = (
            f"Export is {export_pence:.1f}p/kWh, but the battery is at {battery_soc_pct:.0f}% "
            f"(reserve {min_soc_pct}%). Not enough headroom to sell without risking peak cover."
        )
    else:
        headline = "Not worth selling right now"
        message = (
            f"Export is {export_pence:.1f}p/kWh, below your {threshold_pence:.1f}p threshold. "
            "Holding the battery for self-use saves more than exporting."
        )

    return SellOpportunity(
        worth_selling=worth_selling,
        battery_soc_pct=battery_soc_pct,
        export_rate_pence=export_pence,
        import_rate_pence=import_pence,
        threshold_pence=threshold_pence,
        sellable_kwh=sellable_kwh,
        estimated_value_gbp=estimated_value,
        recommended_mode="feed_in",
        headline=headline,
        message=message,
        configured=True,
    )


class SellAdvisorService:
    async def get_opportunity(self, adapter: InverterAdapter) -> SellOpportunity:
        try:
            metrics = await adapter.get_live_metrics()
            soc = metrics.battery_soc_pct
        except Exception:  # noqa: BLE001 — never break the dashboard
            soc = 0.0

        export_rate: float | None = None
        import_rate: float | None = None
        configured = octopus_client.configured()
        if configured:
            try:
                export_rate = await octopus_client.get_export_rate_gbp()
            except Exception:  # noqa: BLE001
                export_rate = None
            try:
                import_rate = await octopus_client.get_import_rate_gbp()
            except Exception:  # noqa: BLE001
                import_rate = None

        return evaluate_sell_opportunity(
            battery_soc_pct=soc,
            export_rate_gbp=export_rate,
            import_rate_gbp=import_rate,
            threshold_gbp=settings.sell_export_threshold_gbp,
            min_soc_pct=settings.sell_min_soc_pct,
            capacity_kwh=settings.battery_capacity_kwh,
            configured=configured,
        )


sell_advisor_service = SellAdvisorService()
