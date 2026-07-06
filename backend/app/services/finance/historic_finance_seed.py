"""Seed personal finance figures from the original finance dashboard plan.

These are placeholder historic values (source=manual) until Open Banking replaces them.
QuickFile-synced business accounts are never touched.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BusinessFinanceSnapshotRow,
    FinanceAccountRow,
    FinanceLiabilityRow,
    PersonalFinanceSnapshotRow,
)
from app.schemas.finance import (
    BusinessFinanceSnapshotCreate,
    FinanceAccountCreate,
    FinanceAccountSource,
    FinanceAccountType,
    FinanceLiabilityCreate,
    FinanceScope,
    PersonalFinanceSnapshotCreate,
)
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_liabilities_service import finance_liabilities_service
from app.services.finance.finance_overview_service import finance_overview_service

HISTORIC_SEED_MARKER = "historic-seed-v1"

PERSONAL_ACCOUNTS: list[dict] = [
    {
        "name": "Lloyds personal",
        "account_type": FinanceAccountType.CURRENT,
        "provider": "Lloyds",
        "balance_gbp": 2500.0,
        "external_id": f"{HISTORIC_SEED_MARKER}:lloyds-personal",
    },
    {
        "name": "Workplace pension",
        "account_type": FinanceAccountType.PENSION,
        "provider": "Aviva",
        "balance_gbp": 50000.0,
        "external_id": f"{HISTORIC_SEED_MARKER}:pension",
    },
    {
        "name": "Greenacre (house value)",
        "account_type": FinanceAccountType.PROPERTY,
        "provider": "Manual estimate",
        "balance_gbp": 425000.0,
        "external_id": f"{HISTORIC_SEED_MARKER}:property",
    },
]

PERSONAL_LIABILITIES: list[dict] = [
    {
        "name": "Virgin Money",
        "debt_type": "credit_card",
        "balance_gbp": 450.0,
        "interest_rate_pct": 24.9,
        "minimum_payment_gbp": 25.0,
        "notes": HISTORIC_SEED_MARKER,
    },
    {
        "name": "Personal MBNA",
        "debt_type": "credit_card",
        "balance_gbp": 350.0,
        "interest_rate_pct": 22.9,
        "minimum_payment_gbp": 15.0,
        "notes": HISTORIC_SEED_MARKER,
    },
    {
        "name": "Personal loan",
        "debt_type": "loan",
        "balance_gbp": 400.0,
        "interest_rate_pct": 7.9,
        "minimum_payment_gbp": 50.0,
        "notes": HISTORIC_SEED_MARKER,
    },
    {
        "name": "Mortgage",
        "debt_type": "mortgage",
        "balance_gbp": 150000.0,
        "interest_rate_pct": 4.49,
        "minimum_payment_gbp": 890.0,
        "notes": HISTORIC_SEED_MARKER,
    },
]

PERSONAL_SNAPSHOT = PersonalFinanceSnapshotCreate(
    snapshot_date=datetime.now(timezone.utc).strftime("%Y-%m"),
    monthly_income_gbp=4000.0,
    monthly_spending_gbp=2200.0,
    household_bills_gbp=700.0,
    debt_repayments_gbp=300.0,
    notes=HISTORIC_SEED_MARKER,
)

BUSINESS_SNAPSHOT = BusinessFinanceSnapshotCreate(
    snapshot_date=datetime.now(timezone.utc).strftime("%Y-%m"),
    turnover_gbp=12000.0,
    expenses_gbp=6500.0,
    vat_reserve_gbp=500.0,
    corp_tax_reserve_gbp=300.0,
    debtors_gbp=8883.42,
    creditors_gbp=1200.0,
    notes=HISTORIC_SEED_MARKER,
)


class HistoricFinanceSeedResult:
    def __init__(
        self,
        *,
        accounts_created: int,
        liabilities_created: int,
        snapshot_created: bool,
        skipped: bool,
        message: str,
    ) -> None:
        self.accounts_created = accounts_created
        self.liabilities_created = liabilities_created
        self.snapshot_created = snapshot_created
        self.skipped = skipped
        self.message = message


async def _has_historic_seed(db: AsyncSession) -> bool:
    marker = await db.scalar(
        select(FinanceAccountRow.id)
        .where(FinanceAccountRow.external_id == PERSONAL_ACCOUNTS[0]["external_id"])
        .limit(1)
    )
    return marker is not None


async def _ensure_missing_seed_rows(db: AsyncSession) -> None:
    """Add newer historic rows (property, business snapshot) without full re-seed."""
    for spec in PERSONAL_ACCOUNTS:
        existing = await db.scalar(
            select(FinanceAccountRow.id)
            .where(FinanceAccountRow.external_id == spec["external_id"])
            .limit(1)
        )
        if existing is not None:
            continue
        await finance_accounts_service.create(
            db,
            FinanceAccountCreate(
                scope=FinanceScope.PERSONAL,
                account_type=spec["account_type"],
                name=spec["name"],
                provider=spec["provider"],
                balance_gbp=spec["balance_gbp"],
                source=FinanceAccountSource.MANUAL,
                external_id=spec["external_id"],
                notes=HISTORIC_SEED_MARKER,
            ),
        )

    existing_business = await db.scalar(
        select(BusinessFinanceSnapshotRow.id)
        .where(
            BusinessFinanceSnapshotRow.snapshot_date == BUSINESS_SNAPSHOT.snapshot_date,
            BusinessFinanceSnapshotRow.notes == HISTORIC_SEED_MARKER,
        )
        .limit(1)
    )
    if existing_business is None:
        await finance_overview_service.create_business_snapshot(db, BUSINESS_SNAPSHOT)


async def seed_historic_finance(
    db: AsyncSession,
    *,
    force: bool = False,
) -> HistoricFinanceSeedResult:
    await _ensure_missing_seed_rows(db)

    if not force and await _has_historic_seed(db):
        return HistoricFinanceSeedResult(
            accounts_created=0,
            liabilities_created=0,
            snapshot_created=False,
            skipped=True,
            message="Historic personal finance data already seeded.",
        )

    accounts_created = 0
    for spec in PERSONAL_ACCOUNTS:
        existing = await db.scalar(
            select(FinanceAccountRow.id)
            .where(FinanceAccountRow.external_id == spec["external_id"])
            .limit(1)
        )
        if existing is not None:
            continue
        await finance_accounts_service.create(
            db,
            FinanceAccountCreate(
                scope=FinanceScope.PERSONAL,
                account_type=spec["account_type"],
                name=spec["name"],
                provider=spec["provider"],
                balance_gbp=spec["balance_gbp"],
                source=FinanceAccountSource.MANUAL,
                external_id=spec["external_id"],
                notes=HISTORIC_SEED_MARKER,
            ),
        )
        accounts_created += 1

    liabilities_created = 0
    for spec in PERSONAL_LIABILITIES:
        existing = await db.scalar(
            select(FinanceLiabilityRow.id)
            .where(
                FinanceLiabilityRow.scope == FinanceScope.PERSONAL.value,
                FinanceLiabilityRow.name == spec["name"],
                FinanceLiabilityRow.notes == HISTORIC_SEED_MARKER,
            )
            .limit(1)
        )
        if existing is not None:
            continue
        await finance_liabilities_service.create(
            db,
            FinanceLiabilityCreate(
                scope=FinanceScope.PERSONAL,
                name=spec["name"],
                debt_type=spec["debt_type"],
                balance_gbp=spec["balance_gbp"],
                interest_rate_pct=spec["interest_rate_pct"],
                minimum_payment_gbp=spec["minimum_payment_gbp"],
                notes=spec["notes"],
            ),
        )
        liabilities_created += 1

    snapshot_created = False
    existing_snap = await db.scalar(
        select(PersonalFinanceSnapshotRow.id)
        .where(
            PersonalFinanceSnapshotRow.snapshot_date == PERSONAL_SNAPSHOT.snapshot_date,
            PersonalFinanceSnapshotRow.notes == HISTORIC_SEED_MARKER,
        )
        .limit(1)
    )
    if existing_snap is None:
        await finance_overview_service.create_personal_snapshot(db, PERSONAL_SNAPSHOT)
        snapshot_created = True

    existing_business = await db.scalar(
        select(BusinessFinanceSnapshotRow.id)
        .where(
            BusinessFinanceSnapshotRow.snapshot_date == BUSINESS_SNAPSHOT.snapshot_date,
            BusinessFinanceSnapshotRow.notes == HISTORIC_SEED_MARKER,
        )
        .limit(1)
    )
    if existing_business is None:
        await finance_overview_service.create_business_snapshot(db, BUSINESS_SNAPSHOT)

    return HistoricFinanceSeedResult(
        accounts_created=accounts_created,
        liabilities_created=liabilities_created,
        snapshot_created=snapshot_created,
        skipped=False,
        message=(
            f"Seeded historic personal finance: {accounts_created} accounts, "
            f"{liabilities_created} liabilities"
            + (", monthly snapshot" if snapshot_created else "")
            + ". QuickFile business data unchanged."
        ),
    )
