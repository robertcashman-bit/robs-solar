"""Alert evaluation and persistence."""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_adapter
from app.config import settings
from app.db.models import AlertRow
from app.schemas.domain import AdapterError, LiveMetrics, NotificationSettings
from app.services.iog_schedule import time_to_minutes
from app.services.notification_settings_service import notification_settings_service
from app.services.octopus_client import octopus_client

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self) -> None:
        self._planned_dispatch_count: int | None = None

    async def evaluate(self, db: AsyncSession, metrics: LiveMetrics) -> None:
        notify_config = await notification_settings_service.get_settings(db)
        soc = metrics.battery_soc_pct
        imp = metrics.daily_import_kwh
        rules: list[tuple[str, str, str, bool]] = [
            ("warning", "soc_low", f"Battery SOC below 20% ({soc:.0f}%)", soc < 20),
            ("info", "soc_high", f"Battery SOC above 95% ({soc:.0f}%)", soc > 95),
            ("warning", "import_high", f"Daily grid import above 10 kWh ({imp:.1f})", imp > 10),
        ]

        if metrics.inverter_status.value == "fault":
            rules.append(
                (
                    "critical",
                    "inverter_fault",
                    "Inverter reporting a fault condition",
                    True,
                )
            )

        try:
            connectivity = await get_adapter().get_connectivity()
            if not connectivity.adapter_connected:
                reason = connectivity.degraded_reason or "Inverter offline"
                rules.append(("critical", "offline", reason, True))
        except AdapterError:
            rules.append(("critical", "offline", "Adapter unreachable", True))

        from app.services.tariff_clock import tariff_now

        offpeak_start = time_to_minutes(settings.iog_offpeak_start)
        now_local = tariff_now()
        now_minute = now_local.hour * 60 + now_local.minute
        minutes_to_offpeak = (offpeak_start - now_minute) % (24 * 60)
        if soc < settings.auto_schedule_soc_floor_pct and 0 < minutes_to_offpeak <= 120:
            hours, mins = minutes_to_offpeak // 60, minutes_to_offpeak % 60
            rules.append(
                (
                    "warning",
                    "soc_low_before_offpeak",
                    f"SOC {soc:.0f}% with off-peak in {hours}h {mins}m",
                    True,
                )
            )

        if octopus_client.configured():
            try:
                info = await octopus_client.get_tariff_info()
                if info.tariff_family == "AGILE":
                    rates = await octopus_client.get_agile_rates(hours=1)
                    if rates:
                        current = rates[0]["value_inc_vat"]
                        if current < 0:
                            rules.append(
                                (
                                    "info",
                                    "negative_price",
                                    f"Agile market price negative ({current:.1f}p/kWh)",
                                    True,
                                )
                            )
                        elif current > 35:
                            rules.append(
                                (
                                    "warning",
                                    "price_spike",
                                    f"Agile market price spike ({current:.1f}p/kWh)",
                                    True,
                                )
                            )
            except Exception as exc:
                logger.debug("Octopus agile alert check skipped: %s", exc)

            try:
                export_rate = await octopus_client.get_export_rate_gbp()
                threshold = notify_config.export_price_threshold_pence / 100.0
                if export_rate is not None and export_rate >= threshold:
                    rules.append(
                        (
                            "info",
                            "export_price_high",
                            f"Export rate high ({export_rate * 100:.1f}p/kWh)",
                            True,
                        )
                    )
                # Sell-to-grid opportunity: high export price AND enough battery
                # headroom above the reserve floor to make exporting worthwhile.
                if (
                    export_rate is not None
                    and export_rate >= settings.sell_export_threshold_gbp
                    and soc > settings.sell_min_soc_pct
                ):
                    sellable = max(
                        0.0,
                        (soc - settings.sell_min_soc_pct) / 100.0 * settings.battery_capacity_kwh,
                    )
                    value = sellable * export_rate
                    rules.append(
                        (
                            "info",
                            "sell_opportunity",
                            (
                                f"Worth selling to grid: {export_rate * 100:.1f}p/kWh, "
                                f"~{sellable:.1f} kWh sellable (≈£{value:.2f}). "
                                "Switch to Feed-in mode to export."
                            ),
                            True,
                        )
                    )
            except Exception as exc:
                logger.debug("Octopus export rate alert skipped: %s", exc)

            try:
                dispatches = await octopus_client.get_dispatches()
                planned_count = len(dispatches.planned)
                if (
                    self._planned_dispatch_count is not None
                    and planned_count > self._planned_dispatch_count
                ):
                    rules.append(
                        (
                            "info",
                            "dispatch_available",
                            f"{planned_count} planned IOG dispatch window(s) available",
                            True,
                        )
                    )
                self._planned_dispatch_count = planned_count
            except Exception as exc:
                logger.debug("Octopus dispatch alert skipped: %s", exc)

        for severity, category, message, fire in rules:
            if fire and notification_settings_service.category_enabled(notify_config, category):
                await self._raise_if_new(db, severity, category, message, notify_config)

    async def raise_manual(
        self,
        db: AsyncSession,
        *,
        severity: str,
        category: str,
        message: str,
    ) -> None:
        notify_config = await notification_settings_service.get_settings(db)
        await self._raise_if_new(db, severity, category, message, notify_config)

    async def _raise_if_new(
        self,
        db: AsyncSession,
        severity: str,
        category: str,
        message: str,
        notify_config: NotificationSettings,
    ) -> None:
        recent = await db.execute(
            select(AlertRow)
            .where(AlertRow.category == category, AlertRow.acknowledged.is_(False))
            .order_by(AlertRow.timestamp.desc())
            .limit(1)
        )
        existing = recent.scalar_one_or_none()
        if existing and existing.message == message:
            return
        row = AlertRow(
            timestamp=datetime.now(timezone.utc),
            severity=severity,
            category=category,
            message=message,
            acknowledged=False,
        )
        db.add(row)
        await db.commit()
        await self._notify_webhook(notify_config, severity, category, message)
        await self._notify_smtp(notify_config, severity, category, message)

    async def _notify_webhook(
        self,
        notify_config: NotificationSettings,
        severity: str,
        category: str,
        message: str,
    ) -> None:
        url = notify_config.webhook_url or settings.alert_webhook_url
        if not url:
            return
        payload = {
            "severity": severity,
            "category": category,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(url, json=payload)
        except Exception as exc:
            logger.warning("Alert webhook failed: %s", exc)

    async def _notify_smtp(
        self,
        notify_config: NotificationSettings,
        severity: str,
        category: str,
        message: str,
    ) -> None:
        if not notify_config.smtp_host or not notify_config.email_to:
            return
        msg = EmailMessage()
        msg["Subject"] = f"[Rob's Solar] {severity.upper()}: {category}"
        msg["From"] = notify_config.smtp_user or notify_config.email_to
        msg["To"] = notify_config.email_to
        msg.set_content(
            f"{message}\n\nSeverity: {severity}\nCategory: {category}\n"
            f"Time: {datetime.now(timezone.utc).isoformat()}"
        )
        try:
            with smtplib.SMTP(notify_config.smtp_host, notify_config.smtp_port, timeout=10) as smtp:
                if notify_config.smtp_user and notify_config.smtp_password:
                    smtp.starttls()
                    smtp.login(notify_config.smtp_user, notify_config.smtp_password)
                smtp.send_message(msg)
        except Exception as exc:
            logger.warning("Alert SMTP failed: %s", exc)

    async def list_alerts(self, db: AsyncSession, limit: int = 50) -> list[dict]:
        result = await db.execute(select(AlertRow).order_by(AlertRow.timestamp.desc()).limit(limit))
        rows = result.scalars().all()
        return [
            {
                "id": row.id,
                "timestamp": row.timestamp.isoformat(),
                "severity": row.severity,
                "category": row.category,
                "message": row.message,
                "acknowledged": row.acknowledged,
            }
            for row in rows
        ]

    async def acknowledge(self, db: AsyncSession, alert_id: int) -> dict | None:
        result = await db.execute(select(AlertRow).where(AlertRow.id == alert_id))
        row = result.scalar_one_or_none()
        if not row:
            return None
        row.acknowledged = True
        await db.commit()
        return {"id": row.id, "acknowledged": True}


alert_service = AlertService()
