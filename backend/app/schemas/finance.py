"""Finance domain schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class FinanceScope(str, Enum):
    PERSONAL = "personal"
    BUSINESS = "business"


class FinanceAccountType(str, Enum):
    CURRENT = "current"
    CREDIT_CARD = "credit_card"
    LOAN = "loan"
    MORTGAGE = "mortgage"
    PENSION = "pension"
    DIRECTORS_LOAN = "directors_loan"
    VAT_RESERVE = "vat_reserve"
    CORP_TAX_RESERVE = "corp_tax_reserve"
    CAPITAL_ON_TAP = "capital_on_tap"
    DEBTORS = "debtors"
    CREDITORS = "creditors"
    OTHER = "other"


class FinanceAccountSource(str, Enum):
    MANUAL = "manual"
    OPEN_BANKING = "open_banking"
    QUICKFILE = "quickfile"


class DebtType(str, Enum):
    CREDIT_CARD = "credit_card"
    LOAN = "loan"
    MORTGAGE = "mortgage"
    BUSINESS_LOAN = "business_loan"
    DIRECTORS_LOAN = "directors_loan"
    OTHER = "other"


class CashflowEntryType(str, Enum):
    INCOME = "income"
    BILL = "bill"
    DEBT = "debt"
    TAX_VAT = "tax_vat"
    OTHER = "other"


class FinanceInsightCategory(str, Enum):
    CASHFLOW = "cashflow"
    DEBT = "debt"
    TAX = "tax"
    BUSINESS = "business"
    ENERGY = "energy"


class FinanceInsightSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class FinanceAccount(BaseModel):
    id: int
    scope: FinanceScope
    account_type: FinanceAccountType
    name: str
    provider: str = ""
    balance_gbp: float = 0.0
    credit_limit_gbp: Optional[float] = None
    interest_rate_pct: Optional[float] = None
    minimum_payment_gbp: Optional[float] = None
    notes: str = ""
    source: FinanceAccountSource = FinanceAccountSource.MANUAL
    external_id: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class FinanceAccountCreate(BaseModel):
    scope: FinanceScope
    account_type: FinanceAccountType
    name: str = Field(min_length=1, max_length=128)
    provider: str = ""
    balance_gbp: float = 0.0
    credit_limit_gbp: Optional[float] = None
    interest_rate_pct: Optional[float] = None
    minimum_payment_gbp: Optional[float] = None
    notes: str = ""
    source: FinanceAccountSource = FinanceAccountSource.MANUAL
    external_id: Optional[str] = None


class FinanceAccountUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    balance_gbp: Optional[float] = None
    credit_limit_gbp: Optional[float] = None
    interest_rate_pct: Optional[float] = None
    minimum_payment_gbp: Optional[float] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class FinanceLiability(BaseModel):
    id: int
    scope: FinanceScope
    name: str
    debt_type: DebtType
    balance_gbp: float
    interest_rate_pct: float
    minimum_payment_gbp: float
    overpayment_gbp: float = 0.0
    payment_day: Optional[int] = None
    account_id: Optional[int] = None
    notes: str = ""
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class FinanceLiabilityCreate(BaseModel):
    scope: FinanceScope
    name: str = Field(min_length=1, max_length=128)
    debt_type: DebtType
    balance_gbp: float = Field(ge=0)
    interest_rate_pct: float = Field(ge=0, le=100)
    minimum_payment_gbp: float = Field(ge=0)
    overpayment_gbp: float = Field(default=0, ge=0)
    payment_day: Optional[int] = Field(default=None, ge=1, le=31)
    account_id: Optional[int] = None
    notes: str = ""


class FinanceLiabilityUpdate(BaseModel):
    name: Optional[str] = None
    balance_gbp: Optional[float] = Field(default=None, ge=0)
    interest_rate_pct: Optional[float] = Field(default=None, ge=0, le=100)
    minimum_payment_gbp: Optional[float] = Field(default=None, ge=0)
    overpayment_gbp: Optional[float] = Field(default=None, ge=0)
    payment_day: Optional[int] = Field(default=None, ge=1, le=31)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PersonalFinanceSnapshot(BaseModel):
    id: int
    snapshot_date: str
    monthly_income_gbp: float
    monthly_spending_gbp: float
    household_bills_gbp: float
    debt_repayments_gbp: float
    surplus_deficit_gbp: float
    notes: str = ""
    breakdown: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PersonalFinanceSnapshotCreate(BaseModel):
    snapshot_date: str
    monthly_income_gbp: float = 0.0
    monthly_spending_gbp: float = 0.0
    household_bills_gbp: float = 0.0
    debt_repayments_gbp: float = 0.0
    notes: str = ""
    breakdown: dict[str, Any] = Field(default_factory=dict)


class BusinessFinanceSnapshot(BaseModel):
    id: int
    snapshot_date: str
    turnover_gbp: float
    expenses_gbp: float
    vat_reserve_gbp: float
    corp_tax_reserve_gbp: float
    debtors_gbp: float
    creditors_gbp: float
    profit_estimate_gbp: float
    cash_available_to_draw_gbp: float
    notes: str = ""
    breakdown: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class BusinessFinanceSnapshotCreate(BaseModel):
    snapshot_date: str
    turnover_gbp: float = 0.0
    expenses_gbp: float = 0.0
    vat_reserve_gbp: float = 0.0
    corp_tax_reserve_gbp: float = 0.0
    debtors_gbp: float = 0.0
    creditors_gbp: float = 0.0
    notes: str = ""
    breakdown: dict[str, Any] = Field(default_factory=dict)


class MonthlyBudgetLine(BaseModel):
    id: int
    scope: FinanceScope
    month: str
    category: str
    budgeted_gbp: float
    actual_gbp: float
    remaining_gbp: float = 0.0
    notes: str = ""
    created_at: datetime
    updated_at: datetime


class MonthlyBudgetLineCreate(BaseModel):
    scope: FinanceScope
    month: str
    category: str = Field(min_length=1, max_length=64)
    budgeted_gbp: float = Field(ge=0)
    actual_gbp: float = Field(default=0, ge=0)
    notes: str = ""


class MonthlyBudgetLineUpdate(BaseModel):
    budgeted_gbp: Optional[float] = Field(default=None, ge=0)
    actual_gbp: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None


class CashflowForecastEntry(BaseModel):
    id: int
    scope: FinanceScope
    forecast_date: str
    horizon_days: int
    entry_type: CashflowEntryType
    label: str
    amount_gbp: float
    is_confirmed: bool
    source: str
    created_at: datetime


class CashflowForecastEntryCreate(BaseModel):
    scope: FinanceScope
    forecast_date: str
    horizon_days: int = Field(default=30, ge=30, le=90)
    entry_type: CashflowEntryType
    label: str = Field(min_length=1, max_length=128)
    amount_gbp: float
    is_confirmed: bool = False
    source: str = "manual"


class FinanceInsight(BaseModel):
    id: int
    category: FinanceInsightCategory
    severity: FinanceInsightSeverity
    title: str
    message: str
    status: str
    related_date: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class FinanceOverviewResponse(BaseModel):
    personal_bank_balance_gbp: float
    business_bank_balance_gbp: float
    total_personal_debt_gbp: float
    total_business_debt_gbp: float
    monthly_income_gbp: float
    monthly_spending_gbp: float
    cash_after_bills_gbp: float
    vat_reserve_gbp: float
    corp_tax_reserve_gbp: float
    vat_reserve_warning: bool
    corp_tax_reserve_warning: bool
    credit_card_balances_gbp: float
    loan_balances_gbp: float
    mortgage_balance_gbp: float
    pension_value_gbp: float
    directors_loan_gbp: float
    net_worth_estimate_gbp: float
    monthly_surplus_gbp: float
    insights: list[FinanceInsight] = Field(default_factory=list)


class DebtStrategyRecommendation(BaseModel):
    strategy: str
    headline: str
    message: str
    debts: list[dict[str, Any]] = Field(default_factory=list)
    estimated_debt_free_date: Optional[str] = None


class CashflowForecastResponse(BaseModel):
    horizon_days: int
    starting_balance_gbp: float
    projected_balance_gbp: float
    entries: list[CashflowForecastEntry]
    cash_pressure_warning: bool
    warning_message: str = ""


class FinanceReportsResponse(BaseModel):
    month: str
    personal_snapshot: Optional[PersonalFinanceSnapshot] = None
    business_snapshot: Optional[BusinessFinanceSnapshot] = None
    net_worth_gbp: float
    total_debt_gbp: float
    debt_reduction_gbp: float
    energy_savings_gbp: float
    energy_savings_vs_forecast: str = ""
