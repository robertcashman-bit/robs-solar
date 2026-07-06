"""Unified optimisation recommendations with apply/dismiss and safe automation."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.factory import get_adapter
from app.config import settings
from app.db.models import OptimisationRecommendationRow
from app.schemas.domain import (
    AuditOutcome,
    AutoScheduleConfigRequest,
    HistoryRange,
    OptimisationRecommendation,
    RecommendationApplyResult,
    RecommendationRisk,
    RecommendationsResponse,
    RecommendationStatus,
    RecommendationType,
    UserRole,
)
from app.services.analytics_service import analytics_service
from app.services.audit_service import audit_service
from app.services.auto_schedule_service import auto_schedule_service
from app.services.optimisation_mode_service import optimisation_mode_service
from app.services.safety_settings_service import safety_settings_service
from app.services.system_warnings_service import system_warnings_service
from app.services.tariff_clock import tariff_now
from app.services.tariff_service import tariff_service


class RecommendationsService:
    async def list_for_today(self, db: AsyncSession) -> RecommendationsResponse:
        today = tariff_now().strftime("%Y-%m-%d")
        await self._ensure_generated(db, today)
        rows = await db.scalars(
            select(OptimisationRecommendationRow)
            .where(OptimisationRecommendationRow.date == today)
            .where(OptimisationRecommendationRow.status != RecommendationStatus.DISMISSED.value)
            .order_by(OptimisationRecommendationRow.estimated_extra_saving_gbp.desc())
        )
        return RecommendationsResponse(recommendations=[self._to_schema(r) for r in rows.all()])

    async def apply(
        self,
        db: AsyncSession,
        rec_id: int,
        *,
        username: str,
        role: UserRole,
    ) -> RecommendationApplyResult:
        row = await db.get(OptimisationRecommendationRow, rec_id)
        if row is None:
            return RecommendationApplyResult(success=False, message="Recommendation not found")
        if row.status == RecommendationStatus.APPLIED.value:
            return RecommendationApplyResult(success=True, message="Already applied")

        mode = await optimisation_mode_service.get_settings(db)
        if safety_settings_service.effective_read_only():
            return RecommendationApplyResult(
                success=False,
                message="System is in read-only mode",
                manual_instructions=row.manual_instructions,
            )

        if not row.can_auto_apply:
            return RecommendationApplyResult(
                success=False,
                message="This change must be applied manually on the inverter",
                manual_instructions=row.manual_instructions,
            )

        if mode.mode.value == "read_only":
            return RecommendationApplyResult(
                success=False,
                message="Optimisation mode is read-only — use manual instructions",
                manual_instructions=row.manual_instructions,
            )

        if row.recommendation_type == RecommendationType.MIN_RESERVE.value:
            try:
                proposed = int(row.proposed_setting.replace("%", "").strip())
            except ValueError:
                proposed = settings.auto_schedule_soc_floor_pct
            await auto_schedule_service.set_config(
                db,
                AutoScheduleConfigRequest(enabled=True, soc_floor_pct=proposed),
            )
            audit = await audit_service.record(
                db,
                username=username,
                role=role,
                action="apply_recommendation",
                request_payload={
                    "recommendation_id": rec_id,
                    "type": row.recommendation_type,
                    "proposed": row.proposed_setting,
                    "rollback": row.rollback_value,
                },
                validation_result="valid",
                adapter_response=None,
                outcome=AuditOutcome.SUCCESS,
            )
            row.status = RecommendationStatus.APPLIED.value
            row.applied_at = datetime.now(timezone.utc)
            await db.commit()
            return RecommendationApplyResult(
                success=True,
                message=f"Reserve updated to {proposed}%",
                audit_id=audit.id,
            )

        if row.recommendation_type in (
            RecommendationType.CHARGE_WINDOW.value,
            RecommendationType.GRID_CHARGE.value,
        ):
            await auto_schedule_service.set_config(db, AutoScheduleConfigRequest(enabled=True))
            await auto_schedule_service.run_once(db, get_adapter())
            audit = await audit_service.record(
                db,
                username=username,
                role=role,
                action="apply_recommendation",
                request_payload={"recommendation_id": rec_id, "type": row.recommendation_type},
                validation_result="valid",
                adapter_response=None,
                outcome=AuditOutcome.SUCCESS,
            )
            row.status = RecommendationStatus.APPLIED.value
            row.applied_at = datetime.now(timezone.utc)
            await db.commit()
            return RecommendationApplyResult(
                success=True,
                message="Auto-schedule aligned to recommended charge window",
                audit_id=audit.id,
            )

        return RecommendationApplyResult(
            success=False,
            message="Automatic apply not available for this recommendation type",
            manual_instructions=row.manual_instructions,
        )

    async def dismiss(self, db: AsyncSession, rec_id: int) -> bool:
        row = await db.get(OptimisationRecommendationRow, rec_id)
        if row is None:
            return False
        row.status = RecommendationStatus.DISMISSED.value
        row.dismissed_at = datetime.now(timezone.utc)
        await db.commit()
        return True

    async def _ensure_generated(self, db: AsyncSession, today: str) -> None:
        existing = await db.scalar(
            select(OptimisationRecommendationRow.id)
            .where(OptimisationRecommendationRow.date == today)
            .limit(1)
        )
        if existing is not None:
            return
        await self._generate(db, today)

    async def _generate(self, db: AsyncSession, today: str) -> None:
        tariff = await tariff_service.get_tariff(db)
        summary = await analytics_service.get_summary(db, HistoryRange.DAY)
        warnings = await system_warnings_service.evaluate(db)
        mode = await optimisation_mode_service.get_settings(db)
        now = datetime.now(timezone.utc)
        recs: list[OptimisationRecommendationRow] = []

        high_soc_warn = any(w.id == "battery_not_discharging" for w in warnings.warnings)
        if high_soc_warn and summary.import_kwh > 1.0:
            current = f"{tariff.warning_battery_soc_threshold_pct}%"
            proposed = f"{tariff.battery_minimum_reserve_pct}%"
            est = summary.import_kwh * tariff.import_rate * 0.25
            recs.append(
                OptimisationRecommendationRow(
                    date=today,
                    recommendation_type=RecommendationType.MIN_RESERVE.value,
                    title="Lower battery reserve during the day",
                    current_setting=current,
                    proposed_setting=proposed,
                    reason=(
                        f"Yesterday the battery stayed above {current} while "
                        f"{summary.import_kwh:.1f} kWh was imported from the grid."
                    ),
                    estimated_extra_saving_gbp=round(est, 2),
                    risk_level=RecommendationRisk.MEDIUM.value,
                    status=RecommendationStatus.PENDING.value,
                    manual_instructions=(
                        f"Set battery minimum reserve to {proposed} on the Sunsynk "
                        "inverter (Settings → Battery → SOC)."
                    ),
                    rollback_value=current,
                    calculation_detail=(
                        f"Estimated missed saving = peak import ({summary.import_kwh:.1f} kWh) "
                        f"× 25% × day rate ({tariff.import_rate:.4f})"
                    ),
                    can_auto_apply=mode.allow_auto_reserve_changes,
                    created_at=now,
                )
            )

        if summary.import_kwh > 3.0:
            night = tariff.night_import_rate or tariff.import_rate
            day = tariff.import_rate
            if night < day:
                est = (summary.import_kwh * 0.3) * (day - night)
                recs.append(
                    OptimisationRecommendationRow(
                        date=today,
                        recommendation_type=RecommendationType.CHARGE_WINDOW.value,
                        title="Charge battery from grid overnight",
                        current_setting="Grid charge off or limited",
                        proposed_setting=(f"Charge {tariff.off_peak_start}–{tariff.off_peak_end}"),
                        reason=(
                            f"Your overnight rate ({night:.2f}p/kWh equivalent) is cheaper "
                            f"than daytime, and {summary.import_kwh:.1f} kWh was imported today."
                        ),
                        estimated_extra_saving_gbp=round(est, 2),
                        risk_level=RecommendationRisk.LOW.value,
                        status=RecommendationStatus.PENDING.value,
                        manual_instructions=(
                            f"Set Sunsynk timer 1 to charge from {tariff.off_peak_start} "
                            f"to {tariff.off_peak_end} with grid charge enabled."
                        ),
                        rollback_value="Disable grid charge",
                        calculation_detail="30% of day import shifted to off-peak rate delta",
                        can_auto_apply=mode.allow_auto_charge_window_changes,
                        created_at=now,
                    )
                )

        if summary.pv_kwh > 15 and summary.import_kwh < 2:
            recs.append(
                OptimisationRecommendationRow(
                    date=today,
                    recommendation_type=RecommendationType.MAX_CHARGE.value,
                    title="Avoid overcharging overnight before high solar",
                    current_setting="100% overnight target",
                    proposed_setting="70% overnight target",
                    reason=("High solar expected — leave room in the battery for PV generation."),
                    estimated_extra_saving_gbp=0.0,
                    risk_level=RecommendationRisk.LOW.value,
                    status=RecommendationStatus.PENDING.value,
                    manual_instructions=(
                        "Reduce overnight charge target to ~70% so solar can fill the battery."
                    ),
                    rollback_value="100%",
                    calculation_detail="High PV day — avoid wasted export from full battery",
                    can_auto_apply=False,
                    created_at=now,
                )
            )

        for rec in recs:
            db.add(rec)
        await db.commit()

    @staticmethod
    def _to_schema(row: OptimisationRecommendationRow) -> OptimisationRecommendation:
        return OptimisationRecommendation(
            id=row.id,
            date=row.date,
            recommendation_type=RecommendationType(row.recommendation_type),
            title=row.title,
            current_setting=row.current_setting,
            proposed_setting=row.proposed_setting,
            reason=row.reason,
            estimated_extra_saving_gbp=row.estimated_extra_saving_gbp,
            risk_level=RecommendationRisk(row.risk_level),
            status=RecommendationStatus(row.status),
            manual_instructions=row.manual_instructions,
            rollback_value=row.rollback_value,
            calculation_detail=row.calculation_detail,
            can_auto_apply=row.can_auto_apply,
            created_at=row.created_at,
            applied_at=row.applied_at,
            dismissed_at=row.dismissed_at,
        )


recommendations_service = RecommendationsService()
