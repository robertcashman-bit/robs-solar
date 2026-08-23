"""Backfill missing Lunch Flow posted_on dates from the provider.

Never invents dates. Soft-deletes only irrecoverable stubs (no external_id and
still no recoverable date after a provider pass).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceTransactionRow
from app.integrations.lunchflow_provider import LunchFlowProvider, _transaction_date
from app.services.finance.lunchflow_account_ids import LUNCHFLOW_SOURCES
from app.services.lunchflow_settings_service import lunchflow_settings_service

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _missing_posted_on(value: str | None) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    if not _DATE_RE.match(text[:10]):
        return True
    try:
        datetime.fromisoformat(text[:10])
    except ValueError:
        return True
    return False


class FinanceDateBackfillService:
    async def backfill_lunchflow_dates(
        self,
        db: AsyncSession,
        *,
        persist: bool = True,
        delete_irrecoverable: bool = True,
    ) -> dict[str, Any]:
        """Re-fetch Lunch Flow txs by external_id and fill empty posted_on."""
        config = await lunchflow_settings_service.get_config(db)
        if not config.api_key.strip():
            return {
                "updated": 0,
                "deleted_stubs": 0,
                "still_missing": 0,
                "examined": 0,
                "message": "Lunch Flow is not configured — cannot backfill dates.",
            }

        all_lunchflow = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.is_deleted.is_(False),
                        FinanceTransactionRow.source.in_(tuple(LUNCHFLOW_SOURCES)),
                    )
                )
            ).all()
        )
        missing = [row for row in all_lunchflow if _missing_posted_on(row.posted_on)]

        if not missing:
            return {
                "updated": 0,
                "deleted_stubs": 0,
                "still_missing": 0,
                "examined": 0,
                "message": "No Lunch Flow rows with missing dates.",
            }

        provider = LunchFlowProvider(config)
        raw_by_external: dict[str, dict[str, Any]] = {}
        try:
            accounts = await provider._client.fetch_accounts()
        except Exception as exc:
            return {
                "updated": 0,
                "deleted_stubs": 0,
                "still_missing": len(missing),
                "examined": len(missing),
                "message": f"Lunch Flow fetch failed: {exc}",
            }

        for record in accounts:
            account_id = str(record.get("id") or record.get("accountId") or "")
            if not account_id:
                continue
            try:
                # Wide window so older undated stubs can still be matched.
                txs = await provider._client.fetch_transactions(account_id, since="2020-01-01")
            except Exception:
                continue
            for item in txs:
                external = str(
                    item.get("id")
                    or item.get("transactionId")
                    or item.get("transaction_id")
                    or ""
                ).strip()
                if not external:
                    continue
                payload = dict(item)
                payload.setdefault("account_id", account_id)
                raw_by_external[external] = payload
                raw_by_external[external.lower()] = payload

        updated = 0
        deleted = 0
        still_missing = 0
        now = datetime.now(timezone.utc)
        samples: list[dict[str, Any]] = []

        for row in missing:
            external = (row.external_id or "").strip()
            dated = ""
            if external:
                payload = raw_by_external.get(external) or raw_by_external.get(external.lower())
                if payload is not None:
                    dated = _transaction_date(payload)
            if dated and _DATE_RE.match(dated):
                row.posted_on = dated
                row.updated_at = now
                updated += 1
                if len(samples) < 20:
                    samples.append(
                        {
                            "id": row.id,
                            "external_id": external,
                            "posted_on": dated,
                            "description": row.description,
                        }
                    )
                continue

            # Irrecoverable stub: no external id to retry later.
            if delete_irrecoverable and not external:
                row.is_deleted = True
                row.updated_at = now
                deleted += 1
            else:
                still_missing += 1

        if persist:
            await db.commit()
        else:
            await db.flush()

        return {
            "updated": updated,
            "deleted_stubs": deleted,
            "still_missing": still_missing,
            "examined": len(missing),
            "provider_tx_index": len(raw_by_external) // 2,
            "samples": samples,
            "message": (
                f"Backfilled {updated} date(s), soft-deleted {deleted} irrecoverable "
                f"stub(s), {still_missing} still missing."
            ),
        }


finance_date_backfill_service = FinanceDateBackfillService()
