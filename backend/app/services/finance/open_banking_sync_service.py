"""Import Open Banking personal accounts into finance tables."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow, FinanceLiabilityRow, FinanceTransactionRow
from app.integrations.base import IntegrationNotConfiguredError
from app.integrations.enable_banking_client import EnableBankingClient
from app.integrations.open_banking_provider import OpenBankingProvider
from app.schemas.finance import (
    FinanceAccountSource,
    OpenBankingConfig,
    OpenBankingRequisition,
    OpenBankingSyncResult,
)
from app.services.finance.historic_finance_seed import HISTORIC_SEED_MARKER
from app.services.open_banking_settings_service import open_banking_settings_service


def _account_uid_from_external_id(external_id: str) -> str | None:
    prefix = "openbanking:enable:"
    if external_id.startswith(prefix):
        return external_id[len(prefix) :]
    return None


def _parse_enable_transaction(
    tx: dict,
    *,
    account_id: int,
    account_uid: str,
    synced_at: datetime,
) -> dict:
    entry_ref = str(tx.get("entry_reference") or tx.get("transaction_id") or "")
    if not entry_ref:
        fingerprint = hashlib.sha256(repr(sorted(tx.items())).encode("utf-8")).hexdigest()[:16]
        entry_ref = fingerprint
    external_id = f"openbanking:enable:{account_uid}:{entry_ref}"

    amount_obj = tx.get("transaction_amount") or {}
    try:
        amount = float(amount_obj.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0.0
    indicator = str(tx.get("credit_debit_indicator") or "").upper()
    if indicator == "DBIT":
        amount = -abs(amount)
    else:
        amount = abs(amount)

    remittance = tx.get("remittance_information")
    if isinstance(remittance, list):
        description = " ".join(str(item) for item in remittance if item)
    elif remittance:
        description = str(remittance)
    else:
        description = ""

    creditor = tx.get("creditor") if isinstance(tx.get("creditor"), dict) else {}
    debtor = tx.get("debtor") if isinstance(tx.get("debtor"), dict) else {}
    if amount < 0:
        merchant = str(creditor.get("name") or debtor.get("name") or "")
    else:
        merchant = str(debtor.get("name") or creditor.get("name") or "")

    bank_code = tx.get("bank_transaction_code")
    category = ""
    if isinstance(bank_code, dict):
        category = str(bank_code.get("description") or bank_code.get("code") or "")

    transaction_date = str(
        tx.get("booking_date") or tx.get("transaction_date") or tx.get("value_date") or ""
    )
    if not transaction_date:
        transaction_date = synced_at.date().isoformat()

    reference = str(tx.get("entry_reference") or "")
    is_pending = str(tx.get("status") or "BOOK").upper() != "BOOK"

    return {
        "account_id": account_id,
        "external_id": external_id,
        "transaction_date": transaction_date[:10],
        "description": description[:512],
        "merchant": merchant[:256],
        "amount_gbp": round(amount, 2),
        "category": category[:128],
        "reference": reference[:128],
        "is_pending": is_pending,
        "synced_at": synced_at,
        "created_at": synced_at,
    }


async def _maybe_save_legacy_tokens(db: AsyncSession, provider: OpenBankingProvider) -> None:
    if provider.adapter.provider != "gocardless":
        return
    tokens = provider.adapter.export_tokens()
    expires_raw = tokens.get("access_expires_at")
    expires_at = None
    if isinstance(expires_raw, str) and expires_raw:
        expires_at = datetime.fromisoformat(expires_raw)
    await open_banking_settings_service.save_tokens(
        db,
        access_token=str(tokens.get("access_token") or "") or None,
        refresh_token=str(tokens.get("refresh_token") or "") or None,
        access_expires_at=expires_at,
    )


class OpenBankingSyncService:
    async def sync(self, db: AsyncSession, config: OpenBankingConfig) -> OpenBankingSyncResult:
        provider = OpenBankingProvider(config)
        requisitions = await open_banking_settings_service.list_requisitions(db)
        try:
            accounts = await provider.sync_accounts_for_requisitions(requisitions)
        except IntegrationNotConfiguredError:
            raise
        finally:
            await _maybe_save_legacy_tokens(db, provider)

        synced = 0
        account_rows: list[FinanceAccountRow] = []
        for item in accounts:
            row = await self._upsert_account(db, item)
            if row is not None:
                account_rows.append(row)
            synced += 1

        if synced > 0:
            await self._retire_historic_personal_placeholders(db)

        transactions_synced = 0
        if config.provider == "enable_banking":
            transactions_synced = await self._sync_transactions(
                db,
                config=config,
                requisitions=requisitions,
                account_rows=account_rows,
            )

        await open_banking_settings_service.mark_synced(db)
        provider_label = "Enable Banking" if config.provider == "enable_banking" else "Open Banking"
        message = f"Synced {synced} personal account(s) from {provider_label}"
        if synced > 0:
            message += "; historic placeholders retired"
        if transactions_synced:
            message += f"; {transactions_synced} transaction(s) imported"
        return OpenBankingSyncResult(accounts_synced=synced, message=message)

    async def _sync_transactions(
        self,
        db: AsyncSession,
        *,
        config: OpenBankingConfig,
        requisitions: list[OpenBankingRequisition],
        account_rows: list[FinanceAccountRow],
    ) -> int:
        if not (config.application_id and config.private_key_pem):
            return 0

        client = EnableBankingClient(config)
        date_from = (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat()
        now = datetime.now(timezone.utc)
        imported = 0

        rows_by_uid = {
            uid: row
            for row in account_rows
            if (uid := _account_uid_from_external_id(row.external_id or ""))
        }

        for connection in requisitions:
            if connection.status != "AUTHORIZED" or not connection.account_ids:
                continue
            for account_uid in connection.account_ids:
                row = rows_by_uid.get(account_uid)
                if row is None:
                    row = await db.scalar(
                        select(FinanceAccountRow).where(
                            FinanceAccountRow.external_id == f"openbanking:enable:{account_uid}",
                            FinanceAccountRow.source == FinanceAccountSource.OPEN_BANKING.value,
                        )
                    )
                if row is None:
                    continue
                try:
                    transactions = await client.get_account_transactions(
                        account_uid,
                        date_from=date_from,
                    )
                except Exception:
                    continue
                for tx in transactions:
                    if not isinstance(tx, dict):
                        continue
                    payload = _parse_enable_transaction(
                        tx,
                        account_id=row.id,
                        account_uid=account_uid,
                        synced_at=now,
                    )
                    if await self._upsert_transaction(db, payload):
                        imported += 1
        return imported

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

    async def _upsert_account(self, db: AsyncSession, item: dict) -> FinanceAccountRow | None:
        external_id = str(item.get("external_id") or "")
        row = await db.scalar(
            select(FinanceAccountRow).where(
                FinanceAccountRow.external_id == external_id,
                FinanceAccountRow.source == FinanceAccountSource.OPEN_BANKING.value,
            )
        )
        now = datetime.now(timezone.utc)
        if row is None:
            row = FinanceAccountRow(
                scope=item["scope"],
                account_type=item["account_type"],
                name=item["name"],
                provider=item.get("provider", "Open Banking"),
                balance_gbp=item.get("balance_gbp", 0.0),
                notes=item.get("notes", ""),
                source=FinanceAccountSource.OPEN_BANKING.value,
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
            if HISTORIC_SEED_MARKER in (row.notes or "") or (
                row.external_id or ""
            ).startswith(HISTORIC_SEED_MARKER):
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


open_banking_sync_service = OpenBankingSyncService()
