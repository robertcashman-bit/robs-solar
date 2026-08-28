"""One-shot personal figures Rob has stated, applied to the live finance DB."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database_url import is_postgres_url, resolve_database_url
from app.db.models import AppSettingRow, FinanceAccountRow, FinanceLiabilityRow
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

STATED_PENSION_GBP = 57726.94
STATED_PENSION_NAME = "Pension"
_PENSION_SETTING_KEY = "finance.stated_pension_gbp"

# Confirmed joint mortgage £164,421; Robert is liable for half.
STATED_MORTGAGE_HALF_GBP = 82210.50
STATED_MORTGAGE_JOINT_GBP = 164421.0
STATED_MORTGAGE_NAME = "House mortgage"
STATED_MORTGAGE_NOTES = "Confirmed half-share of £164,421 joint mortgage"
# Leftover from the old placeholder seed — never treat as a real original.
STALE_MORTGAGE_ORIGINAL_GBP = 175000.0
_MORTGAGE_SETTING_KEY = "finance.stated_mortgage_half_gbp"

# Confirmed joint house £700,000; Robert's half-share.
STATED_HOUSE_SHARE_GBP = 350000.0
STATED_HOUSE_JOINT_GBP = 700000.0
STATED_HOUSE_NAME = "House (your half)"
STATED_HOUSE_NOTES = "Confirmed half-share of £700,000 joint property"
_HOUSE_SETTING_KEY = "finance.stated_house_share_gbp"


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
    flag = await db.get(AppSettingRow, _PENSION_SETTING_KEY)
    if flag is None:
        db.add(AppSettingRow(key=_PENSION_SETTING_KEY, value=f"{amount_gbp:.2f}"))
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
        flag = await db.get(AppSettingRow, _PENSION_SETTING_KEY)
        if flag is not None:
            return None
        row = await apply_stated_pension(db)
        logger.info("Recorded personal pension %.2f GBP", row.balance_gbp)
        return row


def _pick_mortgage_row(rows: list[FinanceLiabilityRow]) -> FinanceLiabilityRow | None:
    if not rows:
        return None
    named = next(
        (
            row
            for row in rows
            if row.name.strip().lower().startswith(STATED_MORTGAGE_NAME.lower())
        ),
        None,
    )
    return named or rows[0]


async def apply_stated_mortgage_half(
    db: AsyncSession,
    *,
    amount_gbp: float = STATED_MORTGAGE_HALF_GBP,
) -> FinanceLiabilityRow:
    """Create or update the personal house mortgage to Robert's confirmed half-share."""
    rows = list(
        (
            await db.scalars(
                select(FinanceLiabilityRow).where(
                    FinanceLiabilityRow.scope == "personal",
                    FinanceLiabilityRow.debt_type == "mortgage",
                    FinanceLiabilityRow.is_active.is_(True),
                )
            )
        ).all()
    )
    now = datetime.now(timezone.utc)
    row = _pick_mortgage_row(rows)
    if row is None:
        row = FinanceLiabilityRow(
            scope="personal",
            name=STATED_MORTGAGE_NAME,
            debt_type="mortgage",
            balance_gbp=amount_gbp,
            interest_rate_pct=0.0,
            minimum_payment_gbp=0.0,
            overpayment_gbp=0.0,
            original_balance_gbp=amount_gbp,
            payment_day=None,
            account_id=None,
            notes=STATED_MORTGAGE_NOTES,
            dla_direction=None,
            interest_rate_known=False,
            credit_limit_gbp=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.balance_gbp = amount_gbp
        if "placeholder" in row.name.lower() or not row.name.strip():
            row.name = STATED_MORTGAGE_NAME
        if not row.notes.strip() or "placeholder" in row.notes.lower():
            row.notes = STATED_MORTGAGE_NOTES
        # Clear the stale £175k original leftover without inventing a new figure.
        if (
            row.original_balance_gbp is None
            or abs(float(row.original_balance_gbp) - STALE_MORTGAGE_ORIGINAL_GBP) < 0.01
        ):
            row.original_balance_gbp = amount_gbp
        row.updated_at = now
    flag = await db.get(AppSettingRow, _MORTGAGE_SETTING_KEY)
    if flag is None:
        db.add(AppSettingRow(key=_MORTGAGE_SETTING_KEY, value=f"{amount_gbp:.2f}"))
    else:
        flag.value = f"{amount_gbp:.2f}"
    await db.commit()
    await db.refresh(row)
    return row


async def ensure_stated_mortgage_half() -> FinanceLiabilityRow | None:
    """Apply the stated personal mortgage half once on the live database."""
    if not is_live_finance_database():
        return None
    async with SessionLocal() as db:
        flag = await db.get(AppSettingRow, _MORTGAGE_SETTING_KEY)
        if flag is not None:
            return None
        row = await apply_stated_mortgage_half(db)
        logger.info(
            "Recorded personal mortgage half %.2f GBP (joint %.0f)",
            row.balance_gbp,
            STATED_MORTGAGE_JOINT_GBP,
        )
        return row


async def ensure_clear_stale_mortgage_original() -> FinanceLiabilityRow | None:
    """Replace leftover £175k original_balance on the live mortgage without touching balance."""
    if not is_live_finance_database():
        return None
    async with SessionLocal() as db:
        rows = list(
            (
                await db.scalars(
                    select(FinanceLiabilityRow).where(
                        FinanceLiabilityRow.scope == "personal",
                        FinanceLiabilityRow.debt_type == "mortgage",
                        FinanceLiabilityRow.is_active.is_(True),
                    )
                )
            ).all()
        )
        row = _pick_mortgage_row(rows)
        if row is None or row.original_balance_gbp is None:
            return None
        if abs(float(row.original_balance_gbp) - STALE_MORTGAGE_ORIGINAL_GBP) >= 0.01:
            return None
        row.original_balance_gbp = STATED_MORTGAGE_HALF_GBP
        if not row.notes.strip() or "placeholder" in row.notes.lower():
            row.notes = STATED_MORTGAGE_NOTES
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
        logger.info(
            "Cleared stale mortgage original_balance; left live balance at %.2f",
            row.balance_gbp,
        )
        return row


def _pick_property_row(rows: list[FinanceAccountRow]) -> FinanceAccountRow | None:
    if not rows:
        return None
    named = next(
        (
            row
            for row in rows
            if row.name.strip().lower() == STATED_HOUSE_NAME.lower()
            or "house" in row.name.strip().lower()
        ),
        None,
    )
    return named or rows[0]


async def apply_stated_house_share(
    db: AsyncSession,
    *,
    amount_gbp: float = STATED_HOUSE_SHARE_GBP,
) -> FinanceAccountRow:
    """Create or update the personal house share to Robert's confirmed half."""
    rows = list(
        (
            await db.scalars(
                select(FinanceAccountRow).where(
                    FinanceAccountRow.scope == "personal",
                    FinanceAccountRow.account_type == "property",
                    FinanceAccountRow.is_active.is_(True),
                )
            )
        ).all()
    )
    now = datetime.now(timezone.utc)
    row = _pick_property_row(rows)
    if row is None:
        row = FinanceAccountRow(
            scope="personal",
            account_type="property",
            name=STATED_HOUSE_NAME,
            provider="",
            balance_gbp=amount_gbp,
            notes=STATED_HOUSE_NOTES,
            source="manual",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.balance_gbp = amount_gbp
        if not row.name.strip() or "placeholder" in row.name.lower():
            row.name = STATED_HOUSE_NAME
        if not row.notes.strip() or "placeholder" in row.notes.lower():
            row.notes = STATED_HOUSE_NOTES
        row.updated_at = now
    flag = await db.get(AppSettingRow, _HOUSE_SETTING_KEY)
    if flag is None:
        db.add(AppSettingRow(key=_HOUSE_SETTING_KEY, value=f"{amount_gbp:.2f}"))
    else:
        flag.value = f"{amount_gbp:.2f}"
    await db.commit()
    await db.refresh(row)
    return row


async def ensure_stated_house_share() -> FinanceAccountRow | None:
    """Apply the stated personal house share once on the live database."""
    if not is_live_finance_database():
        return None
    async with SessionLocal() as db:
        flag = await db.get(AppSettingRow, _HOUSE_SETTING_KEY)
        if flag is not None:
            return None
        row = await apply_stated_house_share(db)
        logger.info(
            "Recorded personal house share %.2f GBP (joint %.0f)",
            row.balance_gbp,
            STATED_HOUSE_JOINT_GBP,
        )
        return row
