"""Automation rules — evaluate conditions and fire actions on metric samples."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_adapter
from app.db.models import AppSettingRow
from app.schemas.domain import (
    AutomationRule,
    AutomationRulesResponse,
    ForceBatteryAction,
    ForceBatteryRequest,
    LiveMetrics,
    RuleActionType,
    RuleConditionType,
    UserRole,
)
from app.services.alert_service import alert_service
from app.services.auto_schedule_service import auto_schedule_service
from app.services.control_service import control_service
from app.services.ev_load_detector import ev_load_detector
from app.services.octopus_client import octopus_client
from app.services.safety_settings_service import safety_settings_service

logger = logging.getLogger(__name__)

_KEY = "automation_rules"


class RulesEngine:
    def __init__(self) -> None:
        self._last_fired: dict[str, datetime] = {}

    async def list_rules(self, db: AsyncSession) -> AutomationRulesResponse:
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _KEY))
        if row is None:
            return AutomationRulesResponse(rules=[])
        data = json.loads(row.value)
        rules = [AutomationRule.model_validate(item) for item in data]
        return AutomationRulesResponse(rules=rules)

    async def _save_rules(self, db: AsyncSession, rules: list[AutomationRule]) -> None:
        encoded = json.dumps([r.model_dump() for r in rules])
        row = await db.scalar(select(AppSettingRow).where(AppSettingRow.key == _KEY))
        if row is None:
            db.add(AppSettingRow(key=_KEY, value=encoded))
        else:
            row.value = encoded
        await db.commit()

    async def add_rule(self, db: AsyncSession, rule: AutomationRule) -> AutomationRulesResponse:
        current = await self.list_rules(db)
        if not rule.id:
            rule.id = str(uuid.uuid4())[:8]
        rules = [*current.rules, rule]
        await self._save_rules(db, rules)
        return AutomationRulesResponse(rules=rules)

    async def delete_rule(self, db: AsyncSession, rule_id: str) -> AutomationRulesResponse:
        current = await self.list_rules(db)
        rules = [r for r in current.rules if r.id != rule_id]
        await self._save_rules(db, rules)
        return AutomationRulesResponse(rules=rules)

    def _cooldown_ok(self, rule: AutomationRule) -> bool:
        last = self._last_fired.get(rule.id)
        if last is None:
            return True
        return datetime.now(timezone.utc) - last >= timedelta(minutes=rule.cooldown_minutes)

    async def _condition_met(
        self,
        rule: AutomationRule,
        metrics: LiveMetrics,
    ) -> bool:
        if rule.condition == RuleConditionType.SOC_BELOW:
            return metrics.battery_soc_pct < rule.condition_value
        if rule.condition == RuleConditionType.SOC_ABOVE:
            return metrics.battery_soc_pct > rule.condition_value
        if rule.condition == RuleConditionType.CAR_CHARGING:
            return ev_load_detector.car_charging_likely
        if rule.condition == RuleConditionType.DISPATCH_ACTIVE:
            return ev_load_detector.status(metrics).in_dispatch_window
        if rule.condition == RuleConditionType.HOUR_BETWEEN:
            from app.services.tariff_clock import tariff_now

            hour = tariff_now().hour
            start = int(rule.condition_value)
            end = int(rule.condition_value_end or 24)
            if start <= end:
                return start <= hour < end
            return hour >= start or hour < end
        if rule.condition == RuleConditionType.EXPORT_RATE_ABOVE:
            if not octopus_client.configured():
                return False
            try:
                rate = await octopus_client.get_export_rate_gbp()
                threshold = rule.condition_value / 100.0
                return rate is not None and rate >= threshold
            except Exception:
                return False
        return False

    async def _execute_action(
        self,
        db: AsyncSession,
        rule: AutomationRule,
    ) -> None:
        if rule.action == RuleActionType.RAISE_ALERT:
            await alert_service.raise_manual(
                db,
                severity="info",
                category="automation_rule",
                message=f"Rule '{rule.name}' fired",
            )
            return

        if rule.action == RuleActionType.SET_AUTO_SCHEDULE:
            from app.schemas.domain import AutoScheduleConfigRequest

            enabled = rule.action_value if rule.action_value is not None else True
            await auto_schedule_service.set_config(db, AutoScheduleConfigRequest(enabled=enabled))
            return

        if (
            safety_settings_service.effective_read_only()
            or not safety_settings_service.effective_enable_live_writes()
        ):
            return

        adapter = get_adapter()
        action_map = {
            RuleActionType.FORCE_BATTERY_CHARGE: ForceBatteryAction.CHARGE,
            RuleActionType.FORCE_BATTERY_DISCHARGE: ForceBatteryAction.DISCHARGE,
            RuleActionType.FORCE_BATTERY_STOP: ForceBatteryAction.STOP,
        }
        fb_action = action_map.get(rule.action)
        if fb_action is None:
            return
        await control_service.force_battery(
            db,
            adapter,
            username="rules-engine",
            role=UserRole.ADMIN,
            request=ForceBatteryRequest(action=fb_action),
        )

    async def evaluate(self, db: AsyncSession, metrics: LiveMetrics) -> None:
        response = await self.list_rules(db)
        for rule in response.rules:
            if not rule.enabled:
                continue
            if not self._cooldown_ok(rule):
                continue
            try:
                if await self._condition_met(rule, metrics):
                    await self._execute_action(db, rule)
                    self._last_fired[rule.id] = datetime.now(timezone.utc)
            except Exception as exc:
                logger.warning("Rule %s failed: %s", rule.id, exc)


rules_engine = RulesEngine()
