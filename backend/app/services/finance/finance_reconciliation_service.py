"""Flag balance-versus-ledger discrepancies. Never auto-edit transactions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow, FinanceChangeAuditRow, FinanceTransactionRow
from app.services.finance.money import from_pence, quantize_gbp, to_pence


class FinanceReconciliationService:
    async def report(self, db: AsyncSession) -> dict[str, Any]:
        accounts = list((await db.scalars(select(FinanceAccountRow))).all())
        txs = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(FinanceTransactionRow.is_deleted.is_(False))
                )
            ).all()
        )
        by_account: dict[int | None, list[FinanceTransactionRow]] = {}
        for row in txs:
            by_account.setdefault(row.account_id, []).append(row)
        flags: list[dict[str, Any]] = []
        for account in accounts:
            ledger_net = from_pence(
                sum(item.amount_pence for item in by_account.get(account.id, []))
            )
            confirmed = float(account.balance_gbp or 0)
            prior = await self._prior_confirmed_balance(db, account.id)
            subsequent = [
                item
                for item in by_account.get(account.id, [])
                if prior and item.created_at and prior["at"] and item.created_at > prior["at"]
            ]
            subsequent_sum = from_pence(sum(item.amount_pence for item in subsequent))
            if prior:
                expected = (quantize_gbp((prior["balance"] or 0) + subsequent_sum) or 0.0)
                discrepancy = quantize_gbp(confirmed - expected)
                if discrepancy not in (None, 0.0):
                    flags.append(
                        {
                            "kind": "balance_vs_subsequent_txs",
                            "account_id": account.id,
                            "account_name": account.name,
                            "confirmed_balance_gbp": confirmed,
                            "expected_gbp": expected,
                            "discrepancy_gbp": discrepancy,
                            "status": "needs_review",
                        }
                    )
            elif by_account.get(account.id):
                flags.append(
                    {
                        "kind": "opening_balance_unknown",
                        "account_id": account.id,
                        "account_name": account.name,
                        "confirmed_balance_gbp": confirmed,
                        "ledger_net_gbp": ledger_net,
                        "status": "insufficient_data",
                    }
                )
        return {
            "flags": flags,
            "account_count": len(accounts),
            "transaction_count": len(txs),
            "auto_edited": False,
        }

    async def _prior_confirmed_balance(
        self, db: AsyncSession, account_id: int
    ) -> dict[str, Any] | None:
        rows = list(
            (
                await db.scalars(
                    select(FinanceChangeAuditRow)
                    .where(
                        FinanceChangeAuditRow.entity_type == "account",
                        FinanceChangeAuditRow.entity_id == str(account_id),
                        FinanceChangeAuditRow.field == "balance_gbp",
                    )
                    .order_by(FinanceChangeAuditRow.created_at.desc())
                )
            ).all()
        )
        if len(rows) < 2:
            return None
        previous = rows[1]
        pence = to_pence(previous.new_value)
        if pence is None:
            return None
        return {"balance": from_pence(pence), "at": previous.created_at}


finance_reconciliation_service = FinanceReconciliationService()
