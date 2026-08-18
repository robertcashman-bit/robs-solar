"""Lunch Flow account alias rows must collapse so overview cash is not 3×."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import FinanceAccountRow, FinanceLiabilityRow
from app.db.session import SessionLocal
from app.schemas.finance import DebtType, FinanceAccountType, FinanceScope, LunchFlowConfig
from app.services.finance.finance_accounts_service import finance_accounts_service
from app.services.finance.finance_calc import (
    AccountView,
    compute_totals,
    liabilities_from_schema,
)
from app.services.finance.lunchflow_account_ids import (
    lunchflow_external_id_aliases,
    normalize_lunchflow_external_id,
)
from app.services.finance.lunchflow_sync_service import LunchFlowSyncService


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _add_account(
    db,
    *,
    name: str,
    external_id: str,
    source: str,
    balance: float,
    account_type: str = FinanceAccountType.CURRENT.value,
    updated_at: datetime | None = None,
    scope: str = FinanceScope.PERSONAL.value,
) -> FinanceAccountRow:
    stamp = updated_at or _now()
    row = FinanceAccountRow(
        scope=scope,
        account_type=account_type,
        name=name,
        provider="Lloyds",
        balance_gbp=balance,
        notes="",
        source=source,
        external_id=external_id,
        is_active=True,
        created_at=stamp,
        updated_at=stamp,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


def test_normalize_strips_lunchflow_prefixes() -> None:
    assert normalize_lunchflow_external_id("28085") == "28085"
    assert normalize_lunchflow_external_id("lunchflow:28085") == "28085"
    assert normalize_lunchflow_external_id("lunch_flow:28085") == "28085"
    assert normalize_lunchflow_external_id("  lunchflow:28087  ") == "28087"
    assert lunchflow_external_id_aliases("lunchflow:28085") == frozenset(
        {"28085", "lunchflow:28085", "lunch_flow:28085"}
    )


@pytest.mark.asyncio
async def test_alias_external_ids_collapse_to_one_active(setup_db: None) -> None:
    older = _now() - timedelta(days=2)
    mid = _now() - timedelta(hours=3)
    newest = _now() - timedelta(minutes=5)
    async with SessionLocal() as db:
        legacy = await _add_account(
            db,
            name="Lloyds Personal Current",
            external_id="lunchflow:28087",
            source="lunch_flow",
            balance=-2414.44,
            updated_at=older,
        )
        bare_a = await _add_account(
            db,
            name="Lloyds Personal — Current Account",
            external_id="28087",
            source="lunchflow",
            balance=-2414.44,
            updated_at=mid,
        )
        bare_b = await _add_account(
            db,
            name="Lloyds Personal — Current Account",
            external_id="28087",
            source="lunchflow",
            balance=-2417.65,
            updated_at=newest,
        )

        archived = await finance_accounts_service.dedupe_active_lunchflow_accounts(db)
        assert archived == 2

        active = (
            await db.scalars(
                select(FinanceAccountRow).where(FinanceAccountRow.is_active.is_(True))
            )
        ).all()
        assert len(active) == 1
        keeper = active[0]
        assert keeper.id == bare_b.id
        assert keeper.external_id == "28087"
        assert keeper.source == "lunchflow"
        assert keeper.balance_gbp == -2417.65

        inactive_ids = {
            row.id
            for row in (
                await db.scalars(
                    select(FinanceAccountRow).where(FinanceAccountRow.is_active.is_(False))
                )
            ).all()
        }
        assert inactive_ids == {legacy.id, bare_a.id}


@pytest.mark.asyncio
async def test_overview_cash_not_triple_counted(setup_db: None) -> None:
    """Production-style triple current + triple saver must sum once each."""
    async with SessionLocal() as db:
        for ext, source, name, balance, age_hours in (
            ("lunchflow:28087", "lunch_flow", "Lloyds Personal Current", -2414.44, 48),
            ("28087", "lunchflow", "Lloyds Personal — Current Account", -2414.44, 6),
            ("28087", "lunchflow", "Lloyds Personal — Current Account", -2417.65, 1),
            ("lunchflow:28086", "lunch_flow", "saving", 13.12, 48),
            ("28086", "lunchflow", "Lloyds Personal — saving", 13.12, 6),
            ("28086", "lunchflow", "Lloyds Personal — saving", 13.12, 1),
        ):
            await _add_account(
                db,
                name=name,
                external_id=ext,
                source=source,
                balance=balance,
                updated_at=_now() - timedelta(hours=age_hours),
            )

        accounts = await finance_accounts_service.list_accounts(db)
        assert len(accounts) == 2

        views = [
            AccountView(
                id=a.id,
                scope=a.scope.value,
                account_type=a.account_type.value,
                name=a.name,
                balance_gbp=a.balance_gbp,
                is_active=a.is_active,
                source=a.source.value,
            )
            for a in accounts
        ]
        totals = compute_totals(views, [])
        # One overdrawn current + one positive saver (both typed current by sync).
        assert totals.personal_overdraft_gbp == 2417.65
        assert totals.personal_cash_gbp == 13.12
        personal_bank = round(totals.personal_cash_gbp - totals.personal_overdraft_gbp, 2)
        assert personal_bank == round(13.12 - 2417.65, 2)
        # Must not be the live inflated cache figure.
        assert personal_bank != -7207.17


@pytest.mark.asyncio
async def test_upsert_is_idempotent_across_alias_forms(setup_db: None) -> None:
    async with SessionLocal() as db:
        await _add_account(
            db,
            name="Lloyds Personal Current",
            external_id="lunchflow:28085",
            source="lunch_flow",
            balance=-100.0,
            account_type=FinanceAccountType.CREDIT_CARD.value,
            updated_at=_now() - timedelta(days=1),
        )

        service = LunchFlowSyncService()
        payload = {
            "scope": FinanceScope.PERSONAL.value,
            "account_type": FinanceAccountType.CREDIT_CARD.value,
            "name": "Lloyds Personal — 6754",
            "provider": "Lloyds",
            "balance_gbp": -8974.94,
            "credit_limit_gbp": 10000.0,
            "external_id": "28085",
            "notes": "Synced via Lunch Flow Open Banking",
        }
        await service._upsert_account(db, payload)
        await service._upsert_account(db, payload)
        await finance_accounts_service.dedupe_active_lunchflow_accounts(db)
        await db.commit()

        active = (
            await db.scalars(
                select(FinanceAccountRow).where(FinanceAccountRow.is_active.is_(True))
            )
        ).all()
        assert len(active) == 1
        assert active[0].external_id == "28085"
        assert active[0].source == "lunchflow"
        assert active[0].balance_gbp == -8974.94
        assert active[0].name == "Lloyds Personal — 6754"

        all_rows = (await db.scalars(select(FinanceAccountRow))).all()
        assert len(all_rows) == 1


@pytest.mark.asyncio
async def test_card_liability_not_added_on_top_of_unique_account(
    setup_db: None,
) -> None:
    async with SessionLocal() as db:
        older = await _add_account(
            db,
            name="Lloyds Personal 6754",
            external_id="lunchflow:28085",
            source="lunch_flow",
            balance=8974.94,
            account_type=FinanceAccountType.CREDIT_CARD.value,
            updated_at=_now() - timedelta(days=2),
        )
        mid = await _add_account(
            db,
            name="Lloyds Personal — 6754",
            external_id="28085",
            source="lunchflow",
            balance=8974.94,
            account_type=FinanceAccountType.CREDIT_CARD.value,
            updated_at=_now() - timedelta(hours=5),
        )
        newest = await _add_account(
            db,
            name="Lloyds Personal — 6754",
            external_id="28085",
            source="lunchflow",
            balance=8974.94,
            account_type=FinanceAccountType.CREDIT_CARD.value,
            updated_at=_now() - timedelta(minutes=2),
        )
        liability = FinanceLiabilityRow(
            scope=FinanceScope.PERSONAL.value,
            name="Lloyds Personal — 6754",
            debt_type=DebtType.CREDIT_CARD.value,
            balance_gbp=8974.94,
            interest_rate_pct=22.9,
            minimum_payment_gbp=200,
            overpayment_gbp=0,
            account_id=older.id,
            notes="",
            is_active=True,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(liability)
        await db.commit()

        accounts = await finance_accounts_service.list_accounts(db)
        assert len(accounts) == 1
        assert accounts[0].id == newest.id

        await db.refresh(liability)
        assert liability.account_id == newest.id

        totals = compute_totals(
            [
                AccountView(
                    id=accounts[0].id,
                    scope="personal",
                    account_type="credit_card",
                    name=accounts[0].name,
                    balance_gbp=accounts[0].balance_gbp,
                    is_active=True,
                    source="lunchflow",
                )
            ],
            liabilities_from_schema([liability]),
        )
        assert totals.personal_credit_card_gbp == 8974.94
        assert totals.credit_card_gbp == 8974.94

        # Archived duplicates must still exist (soft archive).
        inactive = (
            await db.scalars(
                select(FinanceAccountRow).where(FinanceAccountRow.is_active.is_(False))
            )
        ).all()
        assert {row.id for row in inactive} == {older.id, mid.id}


@pytest.mark.asyncio
async def test_list_accounts_archives_duplicates_without_live_refresh(
    setup_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = {"n": 0}

    async def boom(_db):
        called["n"] += 1
        raise AssertionError("ensure_fresh must not run")

    monkeypatch.setattr(
        "app.services.finance.finance_live_refresh_service.finance_live_refresh_service.ensure_fresh",
        boom,
    )
    async with SessionLocal() as db:
        await _add_account(
            db,
            name="A",
            external_id="lunchflow:1",
            source="lunch_flow",
            balance=10,
            updated_at=_now() - timedelta(days=1),
        )
        await _add_account(
            db,
            name="B",
            external_id="1",
            source="lunchflow",
            balance=10,
            updated_at=_now(),
        )
        rows = await finance_accounts_service.list_accounts(db)
        assert len(rows) == 1
        assert called["n"] == 0


@pytest.mark.asyncio
async def test_sync_balances_upsert_collapses_aliases(
    setup_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with SessionLocal() as db:
        await _add_account(
            db,
            name="Legacy",
            external_id="lunchflow:99",
            source="lunch_flow",
            balance=1.0,
            updated_at=_now() - timedelta(days=1),
        )

        class FakeProvider:
            def __init__(self, _config):
                pass

            async def sync_accounts(self):
                return [
                    {
                        "scope": "personal",
                        "account_type": "current",
                        "name": "Lloyds Personal — Current Account",
                        "provider": "Lloyds",
                        "balance_gbp": 42.5,
                        "external_id": "99",
                        "notes": "Synced via Lunch Flow Open Banking",
                    }
                ]

        async def noop_mark(_db):
            return None

        monkeypatch.setattr(
            "app.services.finance.lunchflow_sync_service.LunchFlowProvider",
            FakeProvider,
        )
        monkeypatch.setattr(
            "app.services.finance.lunchflow_sync_service.lunchflow_settings_service.mark_synced",
            noop_mark,
        )

        result = await LunchFlowSyncService().sync_balances(
            db, LunchFlowConfig(api_key="test-key")
        )
        assert result.accounts_synced == 1

        active = (
            await db.scalars(
                select(FinanceAccountRow).where(FinanceAccountRow.is_active.is_(True))
            )
        ).all()
        assert len(active) == 1
        assert active[0].external_id == "99"
        assert active[0].balance_gbp == 42.5
        assert active[0].name == "Lloyds Personal — Current Account"
