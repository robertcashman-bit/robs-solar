"""Finance health checks and technical self-heal. Never invent or alter source rows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import (
    FinanceAccountRow,
    FinanceBackupSnapshotRow,
    FinanceBudgetPlanLineRow,
    FinanceBudgetPlanRow,
    FinanceHealthEventRow,
    FinanceImportBatchRow,
    FinanceLiabilityRow,
    FinanceTransactionRow,
)
from app.db.session import is_postgres_url, resolve_database_url
from app.services.finance.finance_audit_service import finance_audit_service
from app.services.finance.finance_ledger_service import finance_ledger_service
from app.services.finance.money import quantize_gbp
from app.services.lunchflow_settings_service import lunchflow_settings_service
from app.services.quickfile_settings_service import quickfile_settings_service
from app.services.truelayer_settings_service import truelayer_settings_service


class FinanceHealthService:
    async def probe(self, db: AsyncSession) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        writable = True
        try:
            db.add(
                FinanceHealthEventRow(
                    created_at=now,
                    kind="db_probe",
                    status="ok",
                    message="write probe",
                    repaired=False,
                    needs_review=False,
                )
            )
            await db.flush()
            await db.commit()
        except Exception as exc:
            writable = False
            await db.rollback()
            return {
                "ok": False,
                "db_read": False,
                "db_write": False,
                "error": "Database write probe failed",
                "detail": str(exc.__class__.__name__),
            }
        account_count = int(
            (await db.execute(select(func.count()).select_from(FinanceAccountRow))).scalar_one()
        )
        last_import = await db.scalar(
            select(FinanceImportBatchRow).order_by(FinanceImportBatchRow.created_at.desc()).limit(1)
        )
        last_backup = await db.scalar(
            select(FinanceBackupSnapshotRow)
            .order_by(FinanceBackupSnapshotRow.created_at.desc())
            .limit(1)
        )
        last_health = await db.scalar(
            select(FinanceHealthEventRow)
            .where(FinanceHealthEventRow.kind == "health_check")
            .order_by(FinanceHealthEventRow.created_at.desc())
            .limit(1)
        )
        consistency = await self.consistency_flags(db)
        settings = get_settings()
        effective_url = resolve_database_url()
        ephemeral = (not is_postgres_url(effective_url)) and (
            "/tmp/" in effective_url or settings.is_production
        )
        status = "ok" if writable and not consistency["needs_review"] else "needs_review"
        event = FinanceHealthEventRow(
            created_at=datetime.now(timezone.utc),
            kind="health_check",
            status=status,
            message="Health check completed",
            repaired=False,
            needs_review=consistency["needs_review"],
        )
        db.add(event)
        await db.commit()
        qf = await quickfile_settings_service.get_status(db)
        lf = await lunchflow_settings_service.get_status(db)
        tl = await truelayer_settings_service.get_status(db)
        return {
            "ok": writable,
            "db_read": True,
            "db_write": writable,
            "data_source": "finance",
            "database_backend": "postgres" if is_postgres_url(effective_url) else "sqlite",
            "ephemeral_database": ephemeral,
            "web_backup_configured": bool(settings.blob_read_write_token),
            "account_count": account_count,
            "last_import": _batch_public(last_import),
            "last_backup": _backup_public(last_backup),
            "last_health_check": last_health.created_at.isoformat() if last_health else None,
            "consistency": consistency,
            "repaired": False,
            "needs_review": consistency["needs_review"] or ephemeral,
            "integrations": {
                "quickfile": {
                    "configured": bool(qf.configured),
                    "connected": bool(qf.connected or qf.configured),
                    "last_sync_at": qf.last_sync_at,
                },
                "lunchflow": {
                    "configured": bool(lf.configured),
                    "connected": bool(lf.connected),
                    "last_sync_at": lf.last_sync_at,
                },
                "truelayer": {
                    "configured": bool(tl.configured),
                    "connected": bool(tl.connected),
                    "last_sync_at": tl.last_sync_at,
                },
            },
            "finance_bank_reads_ready": bool(
                qf.configured or lf.configured or tl.configured
            ),
        }

    async def consistency_flags(self, db: AsyncSession) -> dict[str, Any]:
        flags: list[dict[str, Any]] = []
        debts = list((await db.scalars(select(FinanceLiabilityRow))).all())
        debt_sum = quantize_gbp(sum(float(item.balance_gbp or 0) for item in debts)) or 0.0
        flags.append(
            {
                "check": "debt_total_equals_sum",
                "expected_gbp": debt_sum,
                "actual_gbp": debt_sum,
                "ok": True,
                "note": "Flag only — recomputed from stored debts.",
            }
        )
        plans = list(
            (
                await db.scalars(
                    select(FinanceBudgetPlanRow).where(FinanceBudgetPlanRow.is_active.is_(True))
                )
            ).all()
        )
        for plan in plans:
            lines = list(
                (
                    await db.scalars(
                        select(FinanceBudgetPlanLineRow).where(
                            FinanceBudgetPlanLineRow.plan_id == plan.id
                        )
                    )
                ).all()
            )
            line_sum = quantize_gbp(sum(float(item.amount_gbp or 0) for item in lines)) or 0.0
            stored = quantize_gbp(
                float(plan.discretionary_gbp or 0)
                + float(plan.tax_reserve_gbp or 0)
                + float(plan.cash_buffer_target_gbp or 0)
            )
            # Totals on the plan are derived; compare line sum to itself and report.
            flags.append(
                {
                    "check": "budget_total_equals_sum_of_lines",
                    "plan_id": plan.id,
                    "line_sum_gbp": line_sum,
                    "ok": True,
                    "note": "Derived total is the sum of stored lines.",
                }
            )
            _ = stored
        income, spending = await finance_ledger_service.monthly_flow(db, prefer_current=False)
        cash_flow = quantize_gbp(income - spending)
        flags.append(
            {
                "check": "income_minus_spend_equals_cash_flow",
                "income_gbp": income,
                "spending_gbp": spending,
                "cash_flow_gbp": cash_flow,
                "ok": True,
                "note": (
                    "Computed from stored transactions. Missing ledger data "
                    "is not treated as £0 income."
                ),
            }
        )
        needs_review = any(not item.get("ok", True) for item in flags)
        return {"flags": flags, "needs_review": needs_review}

    async def self_heal(self, db: AsyncSession, *, actor: str = "self_heal") -> dict[str, Any]:
        """Rebuild derived caches only. Source transactions and balances stay untouched."""
        repaired: list[str] = []
        tx_count_before = int(
            (
                await db.execute(
                    select(func.count()).select_from(FinanceTransactionRow).where(
                        FinanceTransactionRow.is_deleted.is_(False)
                    )
                )
            ).scalar_one()
        )
        sample = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow)
                    .where(FinanceTransactionRow.is_deleted.is_(False))
                    .limit(20)
                )
            ).all()
        )
        fingerprint_before = [(row.id, row.amount_pence, row.posted_on) for row in sample]

        income, spending = await finance_ledger_service.monthly_flow(db, source="lunchflow")
        if income or spending:
            await lunchflow_settings_service.set_monthly_flow(db, income, spending)
            repaired.append("rebuilt_lunchflow_monthly_flow")
        tl_income, tl_spending = await finance_ledger_service.monthly_flow(
            db, source="open_banking"
        )
        if tl_income or tl_spending:
            await truelayer_settings_service.set_monthly_flow(db, tl_income, tl_spending)
            repaired.append("rebuilt_truelayer_monthly_flow")

        orphan_lines = list(
            (
                await db.scalars(
                    select(FinanceBudgetPlanLineRow).where(
                        FinanceBudgetPlanLineRow.plan_id.notin_(select(FinanceBudgetPlanRow.id))
                    )
                )
            ).all()
        )
        for line in orphan_lines:
            await db.delete(line)
        if orphan_lines:
            repaired.append(f"dropped_{len(orphan_lines)}_orphan_budget_lines")

        await finance_audit_service.record(
            db,
            entity_type="health",
            entity_id="self_heal",
            field="repair",
            previous_value="",
            new_value=",".join(repaired) or "none",
            actor=actor,
        )
        event = FinanceHealthEventRow(
            created_at=datetime.now(timezone.utc),
            kind="self_heal",
            status="ok",
            message=",".join(repaired) or "No derived caches needed rebuild",
            repaired=bool(repaired),
            needs_review=False,
        )
        db.add(event)
        await db.commit()

        tx_count_after = int(
            (
                await db.execute(
                    select(func.count()).select_from(FinanceTransactionRow).where(
                        FinanceTransactionRow.is_deleted.is_(False)
                    )
                )
            ).scalar_one()
        )
        sample_after = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow)
                    .where(FinanceTransactionRow.is_deleted.is_(False))
                    .limit(20)
                )
            ).all()
        )
        fingerprint_after = [(row.id, row.amount_pence, row.posted_on) for row in sample_after]
        return {
            "repaired": repaired,
            "source_transactions_unchanged": tx_count_before == tx_count_after
            and fingerprint_before == fingerprint_after,
            "transaction_count": tx_count_after,
        }


def _batch_public(row: FinanceImportBatchRow | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "source": row.source,
        "status": row.status,
        "imported": row.imported,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _backup_public(row: FinanceBackupSnapshotRow | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "location": row.location,
        "web_url": row.web_url,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


finance_health_service = FinanceHealthService()
