"""Import Lunch Flow personal accounts and transactions into finance tables."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow, FinanceLiabilityRow, FinanceTransactionRow
from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.lunch_flow_client import LunchFlowClient, LunchFlowError
from app.schemas.finance import FinanceAccountSource, LunchFlowConfig, LunchFlowSyncResult
from app.services.finance.historic_finance_seed import HISTORIC_SEED_MARKER
from app.services.lunch_flow_settings_service import lunch_flow_settings_service


def _infer_account_type(name: str, institution_name: str) -> str:
    haystack = f"{name} {institution_name}".lower()
    if "credit" in haystack or "card" in haystack:
        return "credit_card"
    if "savings" in haystack:
        return "savings"
    return "current"


def _account_record(
    *,
    account: dict,
    balance_gbp: float,
) -> dict:
    account_id = int(account["id"])
    name = str(account.get("name") or "Account")
    institution = str(account.get("institution_name") or "Bank")
    account_type = _infer_account_type(name, institution)
    return {
        "scope": "personal",
        "account_type": account_type,
        "name": name,
        "provider": institution,
        "balance_gbp": round(balance_gbp, 2),
        "external_id": f"lunchflow:{account_id}",
        "notes": f"Synced via Lunch Flow ({institution})",
    }


def _parse_balance_amount(balance: dict) -> float:
    # Spec shape is {"amount": ..., "currency": ...}; older payloads used current/available.
    for key in ("amount", "current", "available"):
        value = balance.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return 0.0


def _transaction_record(
    tx: dict,
    *,
    account_row_id: int,
    account_id: int,
    synced_at: datetime,
) -> dict:
    tx_id = str(tx.get("id") or "")
    if not tx_id:
        fingerprint = hashlib.sha256(
            repr(sorted((str(k), str(v)) for k, v in tx.items())).encode("utf-8")
        ).hexdigest()[:16]
        tx_id = fingerprint
    amount = float(tx.get("amount") or 0)
    merchant = str(tx.get("merchant") or tx.get("merchant_name") or "")
    is_pending = bool(tx.get("isPending") or tx.get("pending"))
    return {
        "account_id": account_row_id,
        "external_id": f"lunchflow:{account_id}:{tx_id}",
        "transaction_date": str(tx.get("date") or synced_at.date().isoformat())[:10],
        "description": str(tx.get("description") or "")[:512],
        "merchant": merchant[:256],
        "amount_gbp": round(amount, 2),
        "category": str(tx.get("category") or "")[:128],
        "reference": tx_id[:128],
        "is_pending": is_pending,
        "synced_at": synced_at,
        "created_at": synced_at,
    }


class LunchFlowSyncService:
    async def sync(self, db: AsyncSession, config: LunchFlowConfig) -> LunchFlowSyncResult:
        if not config.api_key:
            raise IntegrationNotConfiguredError(
                "Lunch Flow is not configured. Add your API key on the Connect banks page."
            )

        client = LunchFlowClient(config)
        try:
            accounts = await client.list_accounts()
        except LunchFlowError as exc:
            raise IntegrationNotConfiguredError(str(exc)) from exc

        now = datetime.now(timezone.utc)
        date_from = (now - timedelta(days=90)).date().isoformat()
        synced_accounts = 0
        synced_transactions = 0
        account_rows: list[FinanceAccountRow] = []

        for account in accounts:
            if str(account.get("status") or "ACTIVE").upper() not in ("ACTIVE", ""):
                continue
            account_id = int(account["id"])
            try:
                balance_body = await client.get_account_balance(account_id)
                balance_gbp = _parse_balance_amount(balance_body)
            except LunchFlowError:
                balance_gbp = 0.0

            record = _account_record(account=account, balance_gbp=balance_gbp)
            row = await self._upsert_account(db, record)
            if row is not None:
                account_rows.append(row)
                synced_accounts += 1

                try:
                    transactions = await client.get_account_transactions(
                        account_id, date_from=date_from
                    )
                except LunchFlowError:
                    transactions = []
                for tx in transactions:
                    payload = _transaction_record(
                        tx,
                        account_row_id=row.id,
                        account_id=account_id,
                        synced_at=now,
                    )
                    if await self._upsert_transaction(db, payload):
                        synced_transactions += 1

        if synced_accounts > 0:
            await self._retire_historic_personal_placeholders(db)

        await lunch_flow_settings_service.mark_synced(db)
        message = f"Synced {synced_accounts} personal account(s) from Lunch Flow"
        if synced_accounts > 0:
            message += "; historic placeholders retired"
        if synced_transactions:
            message += f"; {synced_transactions} transaction(s) imported"
        return LunchFlowSyncResult(
            accounts_synced=synced_accounts,
            transactions_synced=synced_transactions,
            message=message,
        )

    async def _upsert_account(self, db: AsyncSession, item: dict) -> FinanceAccountRow | None:
        external_id = str(item.get("external_id") or "")
        row = await db.scalar(
            select(FinanceAccountRow).where(
                FinanceAccountRow.external_id == external_id,
                FinanceAccountRow.source == FinanceAccountSource.LUNCH_FLOW.value,
            )
        )
        now = datetime.now(timezone.utc)
        if row is None:
            row = FinanceAccountRow(
                scope=item["scope"],
                account_type=item["account_type"],
                name=item["name"],
                provider=item.get("provider", "Lunch Flow"),
                balance_gbp=item.get("balance_gbp", 0.0),
                notes=item.get("notes", ""),
                source=FinanceAccountSource.LUNCH_FLOW.value,
                external_id=external_id,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
        else:
            row.name = item["name"]
            row.provider = item.get("provider", row.provider)
            row.balance_gbp = item.get("balance_gbp", 0.0)
            row.account_type = item["account_type"]
            row.notes = item.get("notes", row.notes)
            row.is_active = True
            row.updated_at = now
        await db.commit()
        await db.refresh(row)
        return row

    async def _upsert_transaction(self, db: AsyncSession, item: dict) -> bool:
        existing = await db.scalar(
            select(FinanceTransactionRow).where(
                FinanceTransactionRow.external_id == item["external_id"]
            )
        )
        if existing is not None:
            existing.description = item["description"]
            existing.merchant = item["merchant"]
            existing.amount_gbp = item["amount_gbp"]
            existing.category = item["category"]
            existing.reference = item["reference"]
            existing.is_pending = item["is_pending"]
            existing.transaction_date = item["transaction_date"]
            existing.synced_at = item["synced_at"]
            await db.commit()
            return False

        db.add(FinanceTransactionRow(**item))
        await db.commit()
        return True

    async def _retire_historic_personal_placeholders(self, db: AsyncSession) -> None:
        now = datetime.now(timezone.utc)
        account_rows = await db.scalars(
            select(FinanceAccountRow).where(
                FinanceAccountRow.scope == "personal",
                FinanceAccountRow.source == FinanceAccountSource.MANUAL.value,
                FinanceAccountRow.is_active.is_(True),
            )
        )
        for row in account_rows.all():
            if HISTORIC_SEED_MARKER in (row.notes or "") or (row.external_id or "").startswith(
                HISTORIC_SEED_MARKER
            ):
                row.is_active = False
                row.updated_at = now

        liability_rows = await db.scalars(
            select(FinanceLiabilityRow).where(
                FinanceLiabilityRow.scope == "personal",
                FinanceLiabilityRow.is_active.is_(True),
            )
        )
        for row in liability_rows.all():
            if HISTORIC_SEED_MARKER in (row.notes or ""):
                row.is_active = False
                row.updated_at = now
        await db.commit()


lunch_flow_sync_service = LunchFlowSyncService()
