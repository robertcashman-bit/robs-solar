"""Recategorise stored transactions; personal and business stay isolated."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import AppSettingRow, FinanceTransactionRow
from app.db.session import SessionLocal
from app.services.finance.category_registry import list_categories
from app.services.finance.finance_ledger_service import finance_ledger_service
from tests.conftest import login


async def _admin(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> str:
    from app.config import settings

    monkeypatch.setattr(settings, "read_only", False)
    data = await login(client, "admin", "admin-pass")
    return data["csrf_token"]


def _import_row(**overrides):
    base = {
        "posted_on": "2026-07-02",
        "amount_gbp": -20.5,
        "description": "TESCO",
        "account_name": "Current",
        "account_external_id": "acc-1",
        "external_id": "tx-personal-1",
        "scope": "personal",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_set_category_persists_and_registers_scoped_name(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    committed = await client.post(
        "/finance/transactions/import/commit",
        json={
            "source": "manual",
            "rows": [
                _import_row(),
                _import_row(
                    external_id="tx-business-1",
                    account_external_id="biz-1",
                    account_name="Business current",
                    description="COUNSEL FEE",
                    scope="business",
                    amount_gbp=-150,
                ),
            ],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert committed.status_code == 200
    assert committed.json()["imported"] == 2

    listed = await client.get("/finance/transactions")
    assert listed.status_code == 200
    by_scope = {row["scope"]: row for row in listed.json()}
    personal_id = by_scope["personal"]["id"]
    business_id = by_scope["business"]["id"]

    updated = await client.post(
        f"/finance/transactions/{personal_id}/category",
        json={"category": "Rob Personal Snacks"},
        headers={"X-CSRF-Token": csrf},
    )
    assert updated.status_code == 200
    assert updated.json()["category"] == "Rob Personal Snacks"
    assert updated.json()["scope"] == "personal"
    assert updated.json()["category_confidence"] == "HIGH"

    refreshed = await client.get("/finance/transactions?scope=personal&q=tesco")
    assert refreshed.json()[0]["category"] == "Rob Personal Snacks"

    personal_cats = await client.get("/finance/categories?scope=personal")
    business_cats = await client.get("/finance/categories?scope=business")
    personal_names = {item["parent"] for item in personal_cats.json()}
    business_names = {item["parent"] for item in business_cats.json()}
    assert "Rob Personal Snacks" in personal_names
    assert "Rob Personal Snacks" not in business_names

    # Business transaction unchanged; new personal name must not leak into it.
    biz_list = await client.get("/finance/transactions?scope=business")
    assert biz_list.json()[0]["id"] == business_id
    assert biz_list.json()[0]["category"] != "Rob Personal Snacks"


@pytest.mark.asyncio
async def test_business_recategorise_does_not_leak_into_personal(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    committed = await client.post(
        "/finance/transactions/import/commit",
        json={
            "source": "manual",
            "rows": [
                _import_row(external_id="p-2", description="SAINSBURY"),
                _import_row(
                    external_id="b-2",
                    account_external_id="biz-2",
                    account_name="Business current",
                    description="LEXISNEXIS",
                    scope="business",
                    amount_gbp=-40,
                ),
            ],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert committed.status_code == 200

    listed = await client.get("/finance/transactions")
    by_scope = {row["scope"]: row for row in listed.json()}

    updated = await client.post(
        f"/finance/transactions/{by_scope['business']['id']}/category",
        json={"category": "Legal research tools"},
        headers={"X-CSRF-Token": csrf},
    )
    assert updated.status_code == 200
    assert updated.json()["category"] == "Legal research tools"

    personal_cats = {
        item["parent"] for item in (await client.get("/finance/categories?scope=personal")).json()
    }
    business_cats = {
        item["parent"] for item in (await client.get("/finance/categories?scope=business")).json()
    }
    assert "Legal research tools" in business_cats
    assert "Legal research tools" not in personal_cats

    personal_tx = await client.get("/finance/transactions?scope=personal&q=sainsbury")
    assert personal_tx.json()[0]["category"] != "Legal research tools"


@pytest.mark.asyncio
async def test_set_category_rejects_empty_and_missing(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf = await _admin(client, monkeypatch)
    committed = await client.post(
        "/finance/transactions/import/commit",
        json={"source": "manual", "rows": [_import_row(external_id="empty-cat")]},
        headers={"X-CSRF-Token": csrf},
    )
    assert committed.status_code == 200
    txn_id = (await client.get("/finance/transactions")).json()[0]["id"]

    empty = await client.post(
        f"/finance/transactions/{txn_id}/category",
        json={"category": "  "},
        headers={"X-CSRF-Token": csrf},
    )
    assert empty.status_code == 400

    missing = await client.post(
        "/finance/transactions/999999/category",
        json={"category": "Food"},
        headers={"X-CSRF-Token": csrf},
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_ledger_service_scope_isolation(setup_db: None) -> None:
    async with SessionLocal() as db:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        personal = FinanceTransactionRow(
            scope="personal",
            account_name="Current",
            posted_on="2026-07-10",
            amount_pence=-1234,
            description="COFFEE",
            txn_type="expense",
            category="Food",
            source="manual",
            fingerprint="fp-personal-cat",
            created_at=now,
            updated_at=now,
        )
        business = FinanceTransactionRow(
            scope="business",
            account_name="Business",
            posted_on="2026-07-11",
            amount_pence=-5000,
            description="HOSTING",
            txn_type="expense",
            category="IT/software",
            source="manual",
            fingerprint="fp-business-cat",
            created_at=now,
            updated_at=now,
        )
        db.add_all([personal, business])
        await db.commit()
        await db.refresh(personal)
        await db.refresh(business)

        await finance_ledger_service.set_category(
            db, personal.id, category="Cafe treats", actor="test"
        )
        await finance_ledger_service.set_category(
            db, business.id, category="Cloud hosting", actor="test"
        )

        personal_names = {
            item["parent"] for item in await list_categories(db, scope="personal")
        }
        business_names = {
            item["parent"] for item in await list_categories(db, scope="business")
        }
        assert "Cafe treats" in personal_names
        assert "Cafe treats" not in business_names
        assert "Cloud hosting" in business_names
        assert "Cloud hosting" not in personal_names

        stored = {
            row.scope: row.category
            for row in (await db.scalars(select(FinanceTransactionRow))).all()
        }
        assert stored["personal"] == "Cafe treats"
        assert stored["business"] == "Cloud hosting"

        # Custom registry JSON must keep scopes separate.
        setting = await db.scalar(
            select(AppSettingRow).where(AppSettingRow.key == "finance.custom_categories")
        )
        assert setting is not None
        assert "Cafe treats" in setting.value
        assert "Cloud hosting" in setting.value
        assert '"scope": "personal"' in setting.value or '"scope":"personal"' in setting.value
        assert '"scope": "business"' in setting.value or '"scope":"business"' in setting.value
