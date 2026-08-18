"""Validate, preview, and atomically commit imported transactions."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    FinanceAccountRow,
    FinanceImportBatchRow,
    FinanceTransactionRow,
)
from app.services.finance.finance_audit_service import finance_audit_service
from app.services.finance.money import from_pence, to_pence

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def transaction_fingerprint(
    *,
    source: str,
    account_key: str,
    posted_on: str,
    amount_pence: int,
    description: str,
    external_id: str,
) -> str:
    raw = "|".join(
        [
            source.strip().lower(),
            account_key.strip().lower(),
            posted_on,
            str(amount_pence),
            description.strip().lower(),
            external_id.strip(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _today() -> date:
    return datetime.now(timezone.utc).date()


class FinanceImportService:
    def validate_row(
        self, item: dict[str, Any], *, source: str
    ) -> tuple[dict[str, Any] | None, str]:
        posted = str(item.get("posted_on") or item.get("date") or "")[:10]
        if not _DATE_RE.match(posted):
            return None, "Invalid or missing date"
        try:
            parsed = date.fromisoformat(posted)
        except ValueError:
            return None, "Impossible date"
        if parsed > _today():
            return None, "Future date"
        if parsed.year < 1990:
            return None, "Impossible date"
        pence = to_pence(item.get("amount_gbp") if "amount_gbp" in item else item.get("amount"))
        if pence is None:
            return None, "Amount is not a number"
        if pence == 0:
            return None, "Zero amount"
        currency = str(item.get("currency") or "GBP").upper()
        if currency not in {"GBP", "GBX", ""}:
            return None, f"Unsupported currency {currency}"
        description = str(item.get("description") or item.get("narrative") or "")[:256]
        external_id = str(item.get("external_id") or item.get("transaction_id") or "")[:128]
        account_key = str(
            item.get("account_external_id")
            or item.get("account_id")
            or item.get("account_name")
            or ""
        )
        if not account_key:
            return None, "Missing account identifier"
        txn_type = "income" if pence > 0 else "expense"
        if str(item.get("txn_type") or item.get("type") or "").lower() == "transfer":
            txn_type = "transfer"
        fingerprint = transaction_fingerprint(
            source=source,
            account_key=account_key,
            posted_on=posted,
            amount_pence=pence,
            description=description,
            external_id=external_id,
        )
        return {
            "posted_on": posted,
            "amount_pence": pence,
            "description": description,
            "external_id": external_id or None,
            "account_key": account_key,
            "account_name": str(item.get("account_name") or "")[:128],
            "scope": str(item.get("scope") or "personal"),
            "source": source,
            "txn_type": txn_type,
            "currency": "GBP",
            "is_transfer": txn_type == "transfer",
            "fingerprint": fingerprint,
            "category": str(item.get("category") or ""),
        }, ""

    async def preview(
        self,
        db: AsyncSession,
        rows: list[dict[str, Any]],
        *,
        source: str,
    ) -> dict[str, Any]:
        accepted: list[dict[str, Any]] = []
        rejects: list[dict[str, Any]] = []
        warnings: list[str] = []
        seen: set[str] = set()
        for index, item in enumerate(rows):
            valid, reason = self.validate_row(item, source=source)
            if valid is None:
                rejects.append({"index": index, "reason": reason, "row": _safe_row(item)})
                continue
            if valid["fingerprint"] in seen:
                rejects.append(
                    {
                        "index": index,
                        "reason": "Duplicate ID or transaction in this import",
                        "row": _safe_row(item),
                    }
                )
                continue
            seen.add(valid["fingerprint"])
            accepted.append(valid)
        existing = await self._existing_fingerprints(db, [row["fingerprint"] for row in accepted])
        new_rows = [row for row in accepted if row["fingerprint"] not in existing]
        duplicates = [row for row in accepted if row["fingerprint"] in existing]
        if duplicates:
            warnings.append(f"{len(duplicates)} likely duplicate(s) will not be imported again")
        dates = [row["posted_on"] for row in accepted]
        money_in = sum(row["amount_pence"] for row in accepted if row["amount_pence"] > 0)
        money_out = sum(-row["amount_pence"] for row in accepted if row["amount_pence"] < 0)
        return {
            "source": source,
            "detected": len(rows),
            "new_count": len(new_rows),
            "duplicate_count": len(duplicates),
            "rejected_count": len(rejects),
            "rejects": rejects,
            "warnings": warnings,
            "date_from": min(dates) if dates else "",
            "date_to": max(dates) if dates else "",
            "money_in_gbp": from_pence(money_in),
            "money_out_gbp": from_pence(money_out),
            "accepted": new_rows,
        }

    async def commit(
        self,
        db: AsyncSession,
        rows: list[dict[str, Any]],
        *,
        source: str,
        actor: str = "import",
        persist: bool = True,
    ) -> dict[str, Any]:
        preview = await self.preview(db, rows, source=source)
        now = datetime.now(timezone.utc)
        batch = FinanceImportBatchRow(
            source=source,
            status="committing",
            detected=preview["detected"],
            imported=0,
            duplicates=preview["duplicate_count"],
            rejected=preview["rejected_count"],
            money_in_pence=to_pence(preview["money_in_gbp"]) or 0,
            money_out_pence=to_pence(preview["money_out_gbp"]) or 0,
            date_from=preview["date_from"],
            date_to=preview["date_to"],
            rejects_json=json.dumps(preview["rejects"]),
            warnings_json=json.dumps(preview["warnings"]),
            created_at=now,
        )
        db.add(batch)
        await db.flush()
        accounts = await self._account_map(db)
        imported = 0
        from app.services.finance.finance_categoriser_service import finance_categoriser_service

        try:
            for item in preview["accepted"]:
                account = accounts.get(item["account_key"]) or accounts.get(item["account_name"])
                scope = (
                    item["scope"]
                    if item["scope"] in {"personal", "business"}
                    else "personal"
                )
                category = item.get("category") or ""
                confidence = ""
                is_transfer = bool(item["is_transfer"])
                if not category:
                    guessed = await finance_categoriser_service.categorise(
                        db, item["description"], scope=scope
                    )
                    category = guessed.get("category") or ""
                    confidence = guessed.get("confidence") or ""
                    if category == "Transfers" or finance_categoriser_service.looks_like_transfer(
                        item["description"]
                    ):
                        is_transfer = True
                        item["txn_type"] = "transfer"
                db.add(
                    FinanceTransactionRow(
                        scope=scope,
                        account_id=account.id if account else None,
                        account_name=item["account_name"] or (account.name if account else ""),
                        external_id=item["external_id"],
                        posted_on=item["posted_on"],
                        amount_pence=item["amount_pence"],
                        description=item["description"],
                        txn_type=item["txn_type"],
                        category=category,
                        category_confidence=confidence,
                        source=source,
                        import_batch_id=batch.id,
                        fingerprint=item["fingerprint"],
                        is_transfer=is_transfer,
                        is_deleted=False,
                        currency="GBP",
                        created_at=now,
                        updated_at=now,
                    )
                )
                imported += 1
            batch.imported = imported
            batch.status = "committed"
            batch.committed_at = datetime.now(timezone.utc)
            await finance_audit_service.record(
                db,
                entity_type="import_batch",
                entity_id=str(batch.id),
                field="status",
                previous_value="preview",
                new_value="committed",
                actor=actor,
            )
            if persist:
                await db.commit()
                try:
                    from app.services.finance.finance_transfer_service import (
                        finance_transfer_service,
                    )

                    await finance_transfer_service.detect_and_mark(db, persist=True)
                except Exception:
                    pass
            else:
                await db.flush()
        except Exception:
            await db.rollback()
            raise
        return {
            **{key: value for key, value in preview.items() if key != "accepted"},
            "batch_id": batch.id,
            "imported": imported,
            "status": "committed",
        }

    async def _existing_fingerprints(self, db: AsyncSession, fingerprints: list[str]) -> set[str]:
        if not fingerprints:
            return set()
        rows = await db.scalars(
            select(FinanceTransactionRow.fingerprint).where(
                FinanceTransactionRow.fingerprint.in_(fingerprints)
            )
        )
        return set(rows.all())

    async def _account_map(self, db: AsyncSession) -> dict[str, FinanceAccountRow]:
        from app.services.finance.lunchflow_account_ids import (
            is_lunchflow_source,
            normalize_lunchflow_external_id,
        )

        rows = (await db.scalars(select(FinanceAccountRow))).all()
        mapping: dict[str, FinanceAccountRow] = {}
        for row in rows:
            if row.external_id:
                mapping[row.external_id] = row
                if is_lunchflow_source(row.source):
                    canonical = normalize_lunchflow_external_id(row.external_id)
                    if canonical:
                        # Prefer an active canonical row when aliases collide.
                        existing = mapping.get(canonical)
                        if existing is None or (
                            not existing.is_active and row.is_active
                        ):
                            mapping[canonical] = row
            mapping[row.name] = row
        return mapping


def _safe_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": str(item.get("posted_on") or item.get("date") or ""),
        "amount": item.get("amount_gbp", item.get("amount")),
        "description": str(item.get("description") or "")[:80],
    }


finance_import_service = FinanceImportService()
