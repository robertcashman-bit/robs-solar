"""One-shot personal figures Rob has stated, applied to the live finance DB."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database_url import is_postgres_url, resolve_database_url
from app.db.models import AppSettingRow, FinanceAccountRow
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

STATED_PENSION_GBP = 57726.94
STATED_PENSION_NAME = "Pension"
_SETTING_KEY = "finance.stated_pension_gbp"


def is_live_finance_database(database_url: str | None = None) -> bool:
    """True for the real app DB. Test and e2e SQLite files are left alone."""
    url = database_url if database_url is not None else resolve_database_url()
    if is_postgres_url(url):
        lowered = url.lower()
        return "pytest" not in lowered and "test_" not in lowered
    name = url.split("?", 1)[0].rsplit("/", 1)[-1]
    if name != "robs_solar.db":
        return False
    return "test_" not in url and "e2e_" not in url


async def apply_stated_pension(
    db: AsyncSession,
    *,
    amount_gbp: float = STATED_PENSION_GBP,
) -> FinanceAccountRow:
    """Create or update the personal Pension account to the stated pot."""
    rows = list(
        (
            await db.scalars(
                select(FinanceAccountRow).where(
                    FinanceAccountRow.scope == "personal",
                    FinanceAccountRow.account_type == "pension",
                    FinanceAccountRow.is_active.is_(True),
                )
            )
        ).all()
    )
    now = datetime.now(timezone.utc)
    named = next(
        (row for row in rows if row.name.strip().lower() == STATED_PENSION_NAME.lower()),
        None,
    )
    row = named or (rows[0] if rows else None)
    if row is None:
        row = FinanceAccountRow(
            scope="personal",
            account_type="pension",
            name=STATED_PENSION_NAME,
            provider="",
            balance_gbp=amount_gbp,
            notes="Stated pension pot",
            source="manual",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.balance_gbp = amount_gbp
        if not row.name.strip():
            row.name = STATED_PENSION_NAME
        row.updated_at = now
    flag = await db.get(AppSettingRow, _SETTING_KEY)
    if flag is None:
        db.add(AppSettingRow(key=_SETTING_KEY, value=f"{amount_gbp:.2f}"))
    else:
        flag.value = f"{amount_gbp:.2f}"
    await db.commit()
    await db.refresh(row)
    return row


async def ensure_stated_pension() -> FinanceAccountRow | None:
    """Apply the stated pension once on the live database."""
    if not is_live_finance_database():
        return None
    async with SessionLocal() as db:
        flag = await db.get(AppSettingRow, _SETTING_KEY)
        if flag is not None:
            return None
        row = await apply_stated_pension(db)
        logger.info("Recorded personal pension %.2f GBP", row.balance_gbp)
        return row
