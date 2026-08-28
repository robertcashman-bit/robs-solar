"""Scoped cashflow plans and overdraft-limit breaches."""

from app.services.finance.cashflow_plan_service import CashflowPlanService


def test_live_business_overdraft_breach_is_flagged() -> None:
    service = CashflowPlanService()
    plan = service._scope_plan(
        scope="business",
        starting_bank=-6296.0,
        overdraft_drawn=6296.0,
        overdraft_limit=5000.0,
        income=2000.0,
        spending=1500.0,
        budget_income=None,
        liabilities=[],
        months=3,
        allow_zero_income=True,
    )
    assert plan.live_breach is True
    assert plan.headroom_gbp < 0
    assert any(issue.kind == "live_overdraft_breach" for issue in plan.issues)


def test_thin_personal_income_marks_plan_incomplete() -> None:
    service = CashflowPlanService()
    plan = service._scope_plan(
        scope="personal",
        starting_bank=-1924.0,
        overdraft_drawn=1924.0,
        overdraft_limit=3000.0,
        income=215.0,
        spending=1800.0,
        budget_income=4000.0,
        liabilities=[],
        months=3,
    )
    assert plan.incomplete is True
    assert plan.live_breach is False
    assert plan.headroom_gbp > 0
    assert any(issue.kind == "income_incomplete" for issue in plan.issues)
    # Incomplete income must not be projected as if it were full salary.
    assert plan.months[0].income_gbp == 0


def test_card_limit_unknown_is_surfaced() -> None:
    from datetime import datetime, timezone

    from app.schemas.finance import DebtType, FinanceLiability, FinanceScope

    now = datetime.now(timezone.utc)
    card = FinanceLiability(
        id=1,
        scope=FinanceScope.PERSONAL,
        name="MBNA",
        debt_type=DebtType.CREDIT_CARD,
        balance_gbp=8000,
        interest_rate_pct=0,
        minimum_payment_gbp=50,
        overpayment_gbp=0,
        interest_rate_known=False,
        credit_limit_gbp=None,
        created_at=now,
        updated_at=now,
    )
    service = CashflowPlanService()
    plan = service._scope_plan(
        scope="personal",
        starting_bank=100.0,
        overdraft_drawn=0.0,
        overdraft_limit=3000.0,
        income=4000.0,
        spending=2000.0,
        budget_income=4000.0,
        liabilities=[card],
        months=3,
    )
    assert any("limit unknown" in warning for warning in plan.card_warnings)
