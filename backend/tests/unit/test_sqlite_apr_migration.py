"""Regression tests for SQLite APR-flag upgrades."""

from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine, text

from app.db.models import FinanceLiabilityRow
from app.db.session import _migrate_sqlite_columns, _sqlite_scalar_default_sql
from app.services.finance.finance_liabilities_service import _to_schema


def test_sqlite_scalar_default_sql_renders_known_apr_flag() -> None:
    column = FinanceLiabilityRow.__table__.c.interest_rate_known
    assert _sqlite_scalar_default_sql(column) == "1"


def test_migrate_adds_interest_rate_known_with_default(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'apr-add.db'}")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE finance_liabilities (id INTEGER PRIMARY KEY, name TEXT)")
        )
        connection.execute(
            text("INSERT INTO finance_liabilities (id, name) VALUES (1, 'Legacy card')")
        )
        _migrate_sqlite_columns(connection)
        value = connection.execute(
            text("SELECT interest_rate_known FROM finance_liabilities WHERE id = 1")
        ).scalar_one()
    assert int(value) == 1


def test_migrate_backfills_null_interest_rate_known(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'apr-null.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE finance_liabilities ("
                "id INTEGER PRIMARY KEY, "
                "interest_rate_known BOOLEAN"
                ")"
            )
        )
        connection.execute(
            text(
                "INSERT INTO finance_liabilities (id, interest_rate_known) "
                "VALUES (1, NULL)"
            )
        )
        _migrate_sqlite_columns(connection)
        value = connection.execute(
            text("SELECT interest_rate_known FROM finance_liabilities WHERE id = 1")
        ).scalar_one()
    assert int(value) == 1


def test_liability_mapper_treats_null_apr_flag_as_known() -> None:
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(
        id=1,
        scope="personal",
        name="Legacy card",
        debt_type="credit_card",
        balance_gbp=640,
        interest_rate_pct=22.9,
        minimum_payment_gbp=25,
        overpayment_gbp=0,
        original_balance_gbp=None,
        payment_day=None,
        account_id=None,
        notes="",
        dla_direction=None,
        interest_rate_known=None,
        credit_limit_gbp=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    assert _to_schema(row).interest_rate_known is True
