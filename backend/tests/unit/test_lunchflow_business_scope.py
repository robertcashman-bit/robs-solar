"""Lunch Flow business connections, QuickFile shadows, and card balances."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.db.models import FinanceAccountRow, FinanceLiabilityRow
from app.db.session import SessionLocal
from app.integrations.lunchflow_provider import LunchFlowProvider
from app.schemas.finance import (
    DebtType,
    FinanceAccountType,
    FinanceScope,
    LunchFlowConfig,
)
from app.services.finance.finance_calc import (
    AccountView,
    LiabilityView,
    company_position,
    compute_totals,
)
from app.services.finance.lunchflow_scope import (
    credit_card_balance_gbp,
    infer_lunchflow_scope,
    parse_quickfile_shadow_map,
    quickfile_strong_match,
)
from app.services.finance.lunchflow_sync_service import LunchFlowSyncService


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.parametrize(
    ("available", "expected_owed"),
    [
        (537.03, 3462.97),
        (None, 8974.94),
    ],
)
def test_credit_card_balance_interprets_available_credit(available, expected_owed) -> None:
    if available is None:
        owed = credit_card_balance_gbp(
            account_type=FinanceAccountType.CREDIT_CARD,
            credit_limit_gbp=10000.0,
            current=8974.94,
            available=None,
            fallback=8974.94,
        )
    else:
        owed = credit_card_balance_gbp(
            account_type=FinanceAccountType.CREDIT_CARD,
            credit_limit_gbp=4000.0,
            current=537.03,
            available=available,
            fallback=537.03,
        )
    assert owed == pytest.approx(expected_owed)


def test_infer_lunchflow_scope_business_institution_and_connection() -> None:
    record = {"connectionId": "18824", "name": "Current"}
    assert (
        infer_lunchflow_scope(
            record,
            display_name="Lloyds — Current",
            provider_name="Lloyds Personal",
            business_connection_ids=frozenset(),
        )
        == FinanceScope.PERSONAL
    )
    assert (
        infer_lunchflow_scope(
            {"connectionId": "23167", "name": "Account 1"},
            display_name="Account 1",
            provider_name="Lloyds Business",
            business_connection_ids=frozenset({"23167"}),
        )
        == FinanceScope.BUSINESS
    )
    assert (
        infer_lunchflow_scope(
            {"name": "Account 1"},
            display_name="Account 1",
            provider_name="Lloyds Business",
            business_connection_ids=frozenset(),
        )
        == FinanceScope.BUSINESS
    )


@pytest.mark.asyncio
async def test_sync_preserves_manual_scope_type_name_and_active(setup_db: None) -> None:
    async with SessionLocal() as db:
        stamp = _now()
        row = FinanceAccountRow(
            scope=FinanceScope.BUSINESS.value,
            account_type=FinanceAccountType.CREDIT_CARD.value,
            name="Defence Legal — Lloyds card 5393",
            provider="Lloyds Business",
            balance_gbp=3462.97,
            credit_limit_gbp=4000.0,
            notes="",
            source="lunchflow",
            external_id="38150",
            exclude_from_totals=True,
            is_active=False,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(row)
        await db.commit()

        service = LunchFlowSyncService()
        await service._upsert_account(
            db,
            {
                "scope": FinanceScope.PERSONAL.value,
                "account_type": FinanceAccountType.CURRENT.value,
                "name": "Account 1",
                "provider": "Lloyds Business",
                "balance_gbp": 537.03,
                "balance_current": 537.03,
                "balance_available": 537.03,
                "credit_limit_gbp": 4000.0,
                "external_id": "38150",
                "notes": "Synced via Lunch Flow Open Banking",
            },
        )
        await db.commit()
        await db.refresh(row)

        assert row.scope == FinanceScope.BUSINESS.value
        assert row.account_type == FinanceAccountType.CREDIT_CARD.value
        assert row.name == "Defence Legal — Lloyds card 5393"
        assert row.is_active is False
        assert row.exclude_from_totals is True
        assert row.balance_gbp == pytest.approx(3462.97)


@pytest.mark.asyncio
async def test_quickfile_shadow_excluded_from_company_totals(setup_db: None) -> None:
    """LF duplicates must not move company position or business debt off QuickFile."""
    async with SessionLocal() as db:
        stamp = _now()
        qf_current = FinanceAccountRow(
            scope=FinanceScope.BUSINESS.value,
            account_type=FinanceAccountType.CURRENT.value,
            name="Lloyds Bank Business Account (QF 1207)",
            provider="QuickFile",
            balance_gbp=-6290.0,
            source="quickfile",
            external_id="qf-1207",
            is_active=True,
            created_at=stamp,
            updated_at=stamp,
        )
        qf_card_acct = FinanceAccountRow(
            scope=FinanceScope.BUSINESS.value,
            account_type=FinanceAccountType.CREDIT_CARD.value,
            name="Lloyds Bank Business Credit Card (QF 1258)",
            provider="QuickFile",
            balance_gbp=3462.97,
            credit_limit_gbp=4000.0,
            source="quickfile",
            external_id="qf-1258",
            is_active=True,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add_all([qf_current, qf_card_acct])
        await db.flush()
        db.add(
            FinanceLiabilityRow(
                scope=FinanceScope.BUSINESS.value,
                name="Lloyds Bank Business Credit Card",
                debt_type=DebtType.CREDIT_CARD.value,
                balance_gbp=3462.97,
                interest_rate_pct=0.0,
                minimum_payment_gbp=0.0,
                account_id=qf_card_acct.id,
                credit_limit_gbp=4000.0,
                is_active=True,
                created_at=stamp,
                updated_at=stamp,
            )
        )
        lf_current = FinanceAccountRow(
            scope=FinanceScope.BUSINESS.value,
            account_type=FinanceAccountType.CURRENT.value,
            name="Account 2",
            provider="Lloyds Business",
            balance_gbp=5000.0,
            source="lunchflow",
            external_id="38151",
            exclude_from_totals=True,
            is_active=True,
            created_at=stamp,
            updated_at=stamp,
        )
        lf_card = FinanceAccountRow(
            scope=FinanceScope.BUSINESS.value,
            account_type=FinanceAccountType.CREDIT_CARD.value,
            name="Account 1",
            provider="Lloyds Business",
            balance_gbp=537.03,
            credit_limit_gbp=4000.0,
            source="lunchflow",
            external_id="38150",
            exclude_from_totals=True,
            is_active=True,
            created_at=stamp,
            updated_at=stamp,
        )
        personal = FinanceAccountRow(
            scope=FinanceScope.PERSONAL.value,
            account_type=FinanceAccountType.CURRENT.value,
            name="Lloyds Personal — Current",
            provider="Lloyds",
            balance_gbp=-2417.65,
            source="lunchflow",
            external_id="28087",
            is_active=True,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add_all([lf_current, lf_card, personal])
        await db.commit()

        accounts = (await db.scalars(select(FinanceAccountRow))).all()
        liabilities = (await db.scalars(select(FinanceLiabilityRow))).all()
        views = [
            AccountView(
                id=a.id,
                scope=a.scope,
                account_type=a.account_type,
                name=a.name,
                balance_gbp=a.balance_gbp,
                credit_limit_gbp=a.credit_limit_gbp,
                is_active=a.is_active,
                source=a.source,
                exclude_from_totals=a.exclude_from_totals,
            )
            for a in accounts
        ]
        debts = [
            LiabilityView(
                id=liability.id,
                scope=liability.scope,
                name=liability.name,
                debt_type=liability.debt_type,
                balance_gbp=liability.balance_gbp,
                interest_rate_pct=liability.interest_rate_pct,
                minimum_payment_gbp=liability.minimum_payment_gbp,
                account_id=liability.account_id,
                credit_limit_gbp=liability.credit_limit_gbp,
                is_active=liability.is_active,
            )
            for liability in liabilities
        ]
        totals = compute_totals(views, debts)
        business_bank = round(totals.business_cash_gbp - totals.business_overdraft_gbp, 2)
        company_pos = company_position(
            business_bank=business_bank,
            debtors=totals.debtors_gbp,
            vat_reserve=totals.vat_reserve_gbp,
            corp_tax_reserve=totals.corp_tax_reserve_gbp,
            business_external_debt=totals.business_debt_gbp,
        )
        personal_bank = round(totals.personal_cash_gbp - totals.personal_overdraft_gbp, 2)

        assert personal_bank == pytest.approx(-2417.65, abs=0.01)
        assert totals.business_debt_gbp == pytest.approx(3462.97)
        assert company_pos == pytest.approx(-9752.97, abs=0.01)

        without_flag = [
            AccountView(
                id=v.id,
                scope=v.scope,
                account_type=v.account_type,
                name=v.name,
                balance_gbp=v.balance_gbp,
                credit_limit_gbp=v.credit_limit_gbp,
                is_active=v.is_active,
                source=v.source,
                exclude_from_totals=False,
            )
            for v in views
        ]
        inflated = compute_totals(without_flag, debts)
        assert inflated.business_cash_gbp == pytest.approx(5000.0)
        assert totals.business_cash_gbp == pytest.approx(0.0)
        assert inflated.total_liabilities_gbp > totals.total_liabilities_gbp


@pytest.mark.asyncio
async def test_explicit_shadow_map_links_lunchflow_to_quickfile(setup_db: None) -> None:
    async with SessionLocal() as db:
        stamp = _now()
        qf = FinanceAccountRow(
            scope=FinanceScope.BUSINESS.value,
            account_type=FinanceAccountType.CURRENT.value,
            name="Lloyds Bank Business Account",
            provider="QuickFile",
            balance_gbp=100.0,
            source="quickfile",
            external_id="qf-1207",
            is_active=True,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(qf)
        await db.commit()

        service = LunchFlowSyncService()
        await service._upsert_account(
            db,
            {
                "scope": FinanceScope.BUSINESS.value,
                "account_type": FinanceAccountType.CURRENT.value,
                "name": "Lloyds Business — Account 3",
                "provider": "Lloyds Business",
                "balance_gbp": 999.0,
                "external_id": "38151",
                "notes": "Synced via Lunch Flow Open Banking",
            },
            quickfile_shadow_map={"38151": qf.id},
        )
        await db.commit()
        lf = await db.scalar(
            select(FinanceAccountRow).where(FinanceAccountRow.external_id == "38151")
        )
        assert lf is not None
        assert lf.exclude_from_totals is True
        assert lf.mirrors_account_id == qf.id


@pytest.mark.asyncio
async def test_type_only_match_does_not_shadow_lunchflow_account(setup_db: None) -> None:
    async with SessionLocal() as db:
        stamp = _now()
        qf = FinanceAccountRow(
            scope=FinanceScope.BUSINESS.value,
            account_type=FinanceAccountType.CURRENT.value,
            name="QF Current",
            provider="QuickFile",
            balance_gbp=100.0,
            source="quickfile",
            external_id="qf-current",
            is_active=True,
            created_at=stamp,
            updated_at=stamp,
        )
        db.add(qf)
        await db.commit()

        service = LunchFlowSyncService()
        await service._upsert_account(
            db,
            {
                "scope": FinanceScope.BUSINESS.value,
                "account_type": FinanceAccountType.CURRENT.value,
                "name": "Small Lloyds Business savings",
                "provider": "Lloyds Business",
                "balance_gbp": 42.0,
                "external_id": "38152",
                "notes": "Synced via Lunch Flow Open Banking",
            },
            quickfile_shadow_map={},
        )
        await db.commit()
        lf = await db.scalar(
            select(FinanceAccountRow).where(FinanceAccountRow.external_id == "38152")
        )
        assert lf is not None
        assert lf.exclude_from_totals is False
        assert lf.mirrors_account_id is None


def test_parse_quickfile_shadow_map_and_strong_match() -> None:
    assert parse_quickfile_shadow_map("38150:10,38151:3") == {
        "38150": 10,
        "38151": 3,
    }
    lf = FinanceAccountRow(
        scope=FinanceScope.BUSINESS.value,
        account_type=FinanceAccountType.CREDIT_CARD.value,
        name="Defence Legal — Lloyds card 5393",
        provider="Lloyds Business",
        balance_gbp=0.0,
        source="lunchflow",
        external_id="38150",
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    qf = FinanceAccountRow(
        scope=FinanceScope.BUSINESS.value,
        account_type=FinanceAccountType.CREDIT_CARD.value,
        name="Lloyds Bank Business Credit Card",
        provider="QuickFile",
        balance_gbp=0.0,
        source="quickfile",
        external_id="1258",
        notes="nominal 1258",
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    assert quickfile_strong_match(lf, qf) is False
    lf.name = "Business card ending 5393"
    qf.name = "Lloyds card 5393"
    assert quickfile_strong_match(lf, qf) is True


@pytest.mark.asyncio
async def test_provider_marks_business_connection_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = LunchFlowProvider(
        LunchFlowConfig(api_key="k", business_connection_ids=["23167"])
    )

    async def fake_accounts():
        return [
            {
                "id": "38150",
                "name": "Account 1",
                "institutionName": "Lloyds",
                "type": "creditCard",
                "connectionId": "23167",
                "creditLimit": 4000,
            },
            {
                "id": "28087",
                "name": "Current",
                "institutionName": "Lloyds Personal",
                "type": "current",
                "connectionId": "18824",
            },
        ]

    async def fake_detail(account_id: str):
        if account_id == "38150":
            return {"current": 537.03, "available": 537.03, "fallback": 537.03}
        return {"current": -2417.65, "available": None, "fallback": -2417.65}

    monkeypatch.setattr(provider._client, "fetch_accounts", fake_accounts)
    monkeypatch.setattr(provider._client, "fetch_balance_detail", fake_detail)
    rows = await provider.sync_accounts()
    by_id = {row["external_id"]: row for row in rows}
    assert by_id["38150"]["scope"] == "business"
    assert by_id["38150"]["account_type"] == "credit_card"
    assert by_id["38150"]["balance_gbp"] == pytest.approx(3462.97)
    assert by_id["28087"]["scope"] == "personal"
