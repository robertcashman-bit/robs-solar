"""Transfer-vs-salary, date keys, and full-ledger data-quality counts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.db.models import FinanceTransactionRow
from app.db.session import SessionLocal
from app.integrations.lunchflow_provider import _normalize_transaction, _transaction_date
from app.services.finance.finance_categoriser_service import finance_categoriser_service
from app.services.finance.finance_data_quality_service import finance_data_quality_service
from app.services.finance.finance_import_service import finance_import_service
from app.services.finance.finance_transfer_service import finance_transfer_service
from app.services.finance.history_budget_service import (
    history_budget_service,
    is_named_one_off_category,
)


def test_transaction_date_maps_value_booking_and_timestamp_keys() -> None:
    assert _transaction_date({"valueDate": "2026-03-01T12:00:00Z"}) == "2026-03-01"
    assert _transaction_date({"transactionDate": "2026-03-02"}) == "2026-03-02"
    assert _transaction_date({"bookingDate": "2026-03-03T00:00:00"}) == "2026-03-03"
    assert _transaction_date({"timestamp": "2026-03-04T09:15:00+00:00"}) == "2026-03-04"
    assert _transaction_date({"date": ""}) == ""
    assert _transaction_date({"date": "", "valueDate": "2026-03-05"}) == "2026-03-05"
    # Empty provider strings must not invent a date.
    assert _transaction_date({"date": "", "valueDate": "", "bookingDate": ""}) == ""


def test_normalize_skips_pending_and_keeps_empty_date_out_of_cutoff() -> None:
    pending = {"isPending": True, "amount": 10, "date": "2026-01-01"}
    assert _normalize_transaction(pending, "2020-01-01") is None
    row = _normalize_transaction(
        {
            "amount": 2500,
            "type": "credit",
            "valueDate": "2026-02-10",
            "id": "tx-salary",
            "description": "SALARY ACME",
        },
        "2020-01-01",
        account_name="Current",
    )
    assert row is not None
    assert row["posted_on"] == "2026-02-10"


def test_salary_credit_not_treated_as_transfer() -> None:
    assert not finance_categoriser_service.looks_like_transfer(
        "BACS CREDIT SALARY ACME LTD"
    )
    assert finance_categoriser_service.looks_like_salary("BACS CREDIT SALARY ACME LTD")
    assert finance_categoriser_service.looks_like_salary("BACS DEFENCE LEGAL SERVICES")
    assert finance_categoriser_service.looks_like_salary("DEFENCELEGAL BACS")
    assert finance_categoriser_service.looks_like_salary("DLS LTD WAGES")
    assert finance_categoriser_service.looks_like_salary("FPS PAYROLL")
    hit = finance_categoriser_service.categorise_description(
        "FPS SALARY ACME LTD", scope="personal"
    )
    assert hit["category"] == "Salary"
    dls = finance_categoriser_service.categorise_description(
        "BACS DEFENCE LEGAL SERVICES", scope="personal"
    )
    assert dls["category"] == "Salary"
    # Own-account wording still counts.
    assert finance_categoriser_service.looks_like_transfer("FASTER PAYMENT TO SAVINGS")
    assert finance_categoriser_service.looks_like_transfer("INTERNAL TRANSFER")
    # Cross-scope needs clearer wording than equal amounts alone.
    assert not finance_categoriser_service.looks_like_cross_scope_transfer(
        "BACS DEFENCE LEGAL SERVICES FPS WAGES ROBERT"
    )
    assert finance_categoriser_service.looks_like_cross_scope_transfer(
        "INTERNAL TRANSFER DIRECTOR LOAN"
    )
    assert finance_categoriser_service.looks_like_cross_scope_transfer(
        "TO MY ACCOUNT DLA"
    )
    assert finance_categoriser_service.looks_like_cross_scope_transfer(
        "FROM MY ACCOUNT"
    )
    assert not finance_categoriser_service.looks_like_cross_scope_transfer(
        "BACS CREDIT"
    )

@pytest.mark.asyncio
async def test_import_salary_fps_credit_is_not_marked_transfer() -> None:
    async with SessionLocal() as db:
        result = await finance_import_service.commit(
            db,
            [
                {
                    "posted_on": "2026-08-01",
                    "amount_gbp": 3200.0,
                    "description": "FPS SALARY ACME LTD",
                    "account_name": "Current",
                    "account_external_id": "acc-salary",
                    "external_id": "salary-1",
                    "scope": "personal",
                },
                {
                    "posted_on": "2026-08-02",
                    "amount_gbp": -50.0,
                    "description": "FASTER PAYMENT TO SAVINGS",
                    "account_name": "Current",
                    "account_external_id": "acc-salary",
                    "external_id": "xfer-1",
                    "scope": "personal",
                },
            ],
            source="lunchflow",
            actor="test",
            persist=True,
        )
        assert result["imported"] == 2
        rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.is_deleted.is_(False)
                    )
                )
            ).all()
        )
        by_ext = {row.external_id: row for row in rows}
        assert by_ext["salary-1"].is_transfer is False
        assert by_ext["salary-1"].category == "Salary"
        assert by_ext["salary-1"].amount_pence > 0
        assert by_ext["xfer-1"].is_transfer is True


@pytest.mark.asyncio
async def test_defence_legal_wage_pair_not_marked_transfer() -> None:
    """Personal credit + matching business wage debit must stay as income/expense."""
    async with SessionLocal() as db:
        result = await finance_import_service.commit(
            db,
            [
                {
                    "posted_on": "2026-08-28",
                    "amount_gbp": -4200.0,
                    "description": "BACS WAGES ROBERT CASHMAN",
                    "account_name": "Business Current",
                    "account_external_id": "acc-biz",
                    "external_id": "biz-wage-out",
                    "scope": "business",
                },
                {
                    "posted_on": "2026-08-28",
                    "amount_gbp": 4200.0,
                    "description": "BACS DEFENCE LEGAL SERVICES",
                    "account_name": "Personal Current",
                    "account_external_id": "acc-pers",
                    "external_id": "pers-wage-in",
                    "scope": "personal",
                },
                {
                    "posted_on": "2026-08-29",
                    "amount_gbp": -500.0,
                    "description": "INTERNAL TRANSFER TO SAVINGS",
                    "account_name": "Personal Current",
                    "account_external_id": "acc-pers",
                    "external_id": "pers-own-out",
                    "scope": "personal",
                },
                {
                    "posted_on": "2026-08-29",
                    "amount_gbp": 500.0,
                    "description": "INTERNAL TRANSFER FROM CURRENT",
                    "account_name": "Personal Savings",
                    "account_external_id": "acc-save",
                    "external_id": "pers-own-in",
                    "scope": "personal",
                },
            ],
            source="lunchflow",
            actor="test",
            persist=True,
        )
        assert result["imported"] == 4
        rows = list(
            (
                await db.scalars(
                    select(FinanceTransactionRow).where(
                        FinanceTransactionRow.is_deleted.is_(False)
                    )
                )
            ).all()
        )
        by_ext = {row.external_id: row for row in rows}
        assert by_ext["pers-wage-in"].is_transfer is False
        assert by_ext["pers-wage-in"].amount_pence > 0
        assert by_ext["pers-wage-in"].category == "Salary"
        assert by_ext["biz-wage-out"].is_transfer is False
        assert by_ext["pers-own-out"].is_transfer is True
        assert by_ext["pers-own-in"].is_transfer is True


@pytest.mark.asyncio
async def test_unmark_clears_paired_defence_legal_false_transfer() -> None:
    """Already-flagged cross-scope wage pairs return as income without a DB edit."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        biz = FinanceTransactionRow(
            scope="business",
            account_id=None,
            account_name="Business Current",
            external_id="paired-biz-wage",
            posted_on="2026-08-27",
            amount_pence=-380000,
            description="FPS WAGES R CASHMAN",
            txn_type="transfer",
            category="Transfers",
            subcategory="needs_review",
            transfer_group_id="xfer:901-902",
            source="lunchflow",
            fingerprint="fp-paired-biz-wage",
            is_transfer=True,
            is_deleted=False,
            currency="GBP",
            created_at=now,
            updated_at=now,
        )
        personal = FinanceTransactionRow(
            scope="personal",
            account_id=None,
            account_name="Personal Current",
            external_id="paired-pers-wage",
            posted_on="2026-08-27",
            amount_pence=380000,
            description="BACS DEFENCE LEGAL SERVICES",
            txn_type="transfer",
            category="Transfers",
            subcategory="needs_review",
            transfer_group_id="xfer:901-902",
            source="lunchflow",
            fingerprint="fp-paired-pers-wage",
            is_transfer=True,
            is_deleted=False,
            currency="GBP",
            created_at=now,
            updated_at=now,
        )
        db.add(biz)
        db.add(personal)
        await db.commit()

        result = await finance_transfer_service.detect_and_mark(
            db, lookback_days=400, persist=True
        )
        assert result["cleared_false_transfers"] >= 2
        await db.refresh(biz)
        await db.refresh(personal)
        assert personal.is_transfer is False
        assert personal.txn_type == "income"
        assert personal.category == "Salary"
        assert personal.transfer_group_id is None
        assert biz.is_transfer is False
        assert biz.subcategory != "needs_review"


@pytest.mark.asyncio
async def test_unmark_false_transfers_clears_rails_only_salary() -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        false_salary = FinanceTransactionRow(
            scope="personal",
            account_id=None,
            account_name="Current",
            external_id="false-salary",
            posted_on="2026-07-15",
            amount_pence=280000,
            description="BACS CREDIT FROM EMPLOYER SALARY",
            txn_type="transfer",
            category="Transfers",
            source="lunchflow",
            fingerprint="fp-false-salary",
            is_transfer=True,
            is_deleted=False,
            currency="GBP",
            created_at=now,
            updated_at=now,
        )
        paired = FinanceTransactionRow(
            scope="personal",
            account_id=None,
            account_name="Current",
            external_id="paired",
            posted_on="2026-07-16",
            amount_pence=-10000,
            description="MOVE TO SAVINGS",
            txn_type="transfer",
            category="Transfers",
            transfer_group_id="xfer:1-2",
            source="lunchflow",
            fingerprint="fp-paired",
            is_transfer=True,
            is_deleted=False,
            currency="GBP",
            created_at=now,
            updated_at=now,
        )
        db.add(false_salary)
        db.add(paired)
        await db.commit()

        result = await finance_transfer_service.unmark_false_transfers(
            db, persist=True, redetect=False
        )
        assert result["cleared"] >= 1
        await db.refresh(false_salary)
        await db.refresh(paired)
        assert false_salary.is_transfer is False
        assert false_salary.category == "Salary"
        assert paired.is_transfer is True


@pytest.mark.asyncio
async def test_data_quality_counts_full_ledger_including_empty_dates() -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        # Seed > limit dated rows plus undated / uncategorised so a 5000-row
        # DESC sample would miss empty posted_on if it still used that pattern.
        for index in range(60):
            db.add(
                FinanceTransactionRow(
                    scope="personal",
                    account_id=None,
                    account_name="Current",
                    external_id=f"dated-{index}",
                    posted_on=f"2026-08-{(index % 28) + 1:02d}",
                    amount_pence=-1000,
                    description=f"SHOP {index}",
                    txn_type="expense",
                    category="Food",
                    source="lunchflow",
                    fingerprint=f"fp-dated-{index}",
                    is_transfer=False,
                    is_deleted=False,
                    currency="GBP",
                    created_at=now,
                    updated_at=now,
                )
            )
        for index in range(5):
            db.add(
                FinanceTransactionRow(
                    scope="personal",
                    account_id=None,
                    account_name="Current",
                    external_id=f"undated-{index}",
                    posted_on="",
                    amount_pence=-500,
                    description=f"MISSING DATE {index}",
                    txn_type="expense",
                    category="",
                    source="lunchflow",
                    fingerprint=f"fp-undated-{index}",
                    is_transfer=False,
                    is_deleted=False,
                    currency="GBP",
                    created_at=now,
                    updated_at=now,
                )
            )
        await db.commit()
        report = await finance_data_quality_service.report(db, limit=10)
        assert report["full_ledger"] is True
        assert report["missing_dates_count"] >= 5
        assert report["uncategorised_count"] >= 5
        assert report["transaction_count"] >= 65
        assert len(report["missing_dates"]) >= 1
        assert "href" in report["missing_dates"][0]


def test_named_one_off_categories() -> None:
    assert is_named_one_off_category("Solar installation")
    assert is_named_one_off_category("VAT pot")
    assert is_named_one_off_category("VAT transfer")
    assert is_named_one_off_category("Large unusual invoice")
    assert not is_named_one_off_category("Food")
    assert not is_named_one_off_category("Utilities")


@pytest.mark.asyncio
async def test_history_budget_excludes_named_one_offs_from_typical_lines() -> None:
    now = datetime.now(timezone.utc)
    today = now.date()
    async with SessionLocal() as db:
        for months_ago in range(6):
            month = today.month - months_ago
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            db.add(
                FinanceTransactionRow(
                    scope="personal",
                    account_id=None,
                    account_name="Current",
                    external_id=f"food-{months_ago}",
                    posted_on=f"{year:04d}-{month:02d}-10",
                    amount_pence=-4000,
                    description="TESCO",
                    txn_type="expense",
                    category="Food",
                    source="manual",
                    fingerprint=f"fp-food-{months_ago}",
                    is_transfer=False,
                    is_deleted=False,
                    currency="GBP",
                    created_at=now,
                    updated_at=now,
                )
            )
        db.add(
            FinanceTransactionRow(
                scope="personal",
                account_id=None,
                account_name="Current",
                external_id="solar-1",
                posted_on=f"{today.year:04d}-{today.month:02d}-05",
                amount_pence=-500000,
                description="SOLAR PANEL INSTALL",
                txn_type="expense",
                category="Solar installation",
                source="manual",
                fingerprint="fp-solar",
                is_transfer=False,
                is_deleted=False,
                currency="GBP",
                created_at=now,
                updated_at=now,
            )
        )
        await db.commit()
        preview = await history_budget_service.preview(db, "personal")
        categories = {line["category"] for line in preview["lines"]}
        assert "Food" in categories
        assert "Solar installation" not in categories
        one_off_cats = {item["category"] for item in preview["one_offs"]}
        assert "Solar installation" in one_off_cats
