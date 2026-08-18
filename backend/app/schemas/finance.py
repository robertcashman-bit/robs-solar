"""Finance domain schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

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
    PROPERTY = "property"
    OTHER_ASSET = "other_asset"
    OTHER = "other"


class FinanceAccountSource(str, Enum):
    MANUAL = "manual"
    OPEN_BANKING = "open_banking"
    LUNCHFLOW = "lunchflow"
    QUICKFILE = "quickfile"
    FUNDING_CIRCLE = "funding_circle"

    @classmethod
    def _missing_(cls, value: object):
        if value == "lunch_flow":
            return cls.LUNCHFLOW
        return None


class DebtType(str, Enum):
    CREDIT_CARD = "credit_card"
    LOAN = "loan"
    MORTGAGE = "mortgage"
    BUSINESS_LOAN = "business_loan"
    DIRECTORS_LOAN = "directors_loan"
    OTHER = "other"


class DirectorsLoanDirection(str, Enum):
    DIRECTOR_OWES_COMPANY = "director_owes_company"
    COMPANY_OWES_DIRECTOR = "company_owes_director"


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
    credit_limit_gbp: float | None = None
    interest_rate_pct: float | None = None
    minimum_payment_gbp: float | None = None
    notes: str = ""
    source: FinanceAccountSource = FinanceAccountSource.MANUAL
    external_id: str | None = None
    dla_direction: DirectorsLoanDirection | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class FinanceAccountCreate(BaseModel):
    scope: FinanceScope
    account_type: FinanceAccountType
    name: str = Field(min_length=1, max_length=128)
    provider: str = ""
    balance_gbp: float = 0.0
    credit_limit_gbp: float | None = None
    interest_rate_pct: float | None = None
    minimum_payment_gbp: float | None = None
    notes: str = ""
    source: FinanceAccountSource = FinanceAccountSource.MANUAL
    external_id: str | None = None
    dla_direction: DirectorsLoanDirection | None = None


class FinanceAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    provider: str | None = None
    balance_gbp: float | None = None
    credit_limit_gbp: float | None = None
    interest_rate_pct: float | None = None
    minimum_payment_gbp: float | None = None
    notes: str | None = None
    dla_direction: DirectorsLoanDirection | None = None
    is_active: bool | None = None


class FinanceLiability(BaseModel):
    id: int
    scope: FinanceScope
    name: str
    debt_type: DebtType
    balance_gbp: float
    interest_rate_pct: float
    minimum_payment_gbp: float
    overpayment_gbp: float = 0.0
    original_balance_gbp: float | None = None
    payment_day: int | None = None
    account_id: int | None = None
    notes: str = ""
    dla_direction: DirectorsLoanDirection | None = None
    interest_rate_known: bool = True
    credit_limit_gbp: float | None = None
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
    original_balance_gbp: float | None = Field(default=None, ge=0)
    payment_day: int | None = Field(default=None, ge=1, le=31)
    account_id: int | None = None
    notes: str = ""
    dla_direction: DirectorsLoanDirection | None = None
    interest_rate_known: bool = True
    credit_limit_gbp: float | None = Field(default=None, ge=0)


class FinanceLiabilityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    balance_gbp: float | None = Field(default=None, ge=0)
    interest_rate_pct: float | None = Field(default=None, ge=0, le=100)
    minimum_payment_gbp: float | None = Field(default=None, ge=0)
    overpayment_gbp: float | None = Field(default=None, ge=0)
    original_balance_gbp: float | None = Field(default=None, ge=0)
    payment_day: int | None = Field(default=None, ge=1, le=31)
    notes: str | None = None
    dla_direction: DirectorsLoanDirection | None = None
    interest_rate_known: bool | None = None
    credit_limit_gbp: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


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
    actual_gbp: float | None = None
    remaining_gbp: float | None = None
    actual_recorded: bool = False
    notes: str = ""
    created_at: datetime
    updated_at: datetime


class MonthlyBudgetLineCreate(BaseModel):
    scope: FinanceScope
    month: str
    category: str = Field(min_length=1, max_length=64)
    budgeted_gbp: float = Field(ge=0)
    actual_gbp: float | None = Field(default=None, ge=0)
    notes: str = ""


class MonthlyBudgetLineUpdate(BaseModel):
    budgeted_gbp: float | None = Field(default=None, ge=0)
    actual_gbp: float | None = Field(default=None, ge=0)
    notes: str | None = None


class MonthlyBudgetBatchWrite(BaseModel):
    lines: list[MonthlyBudgetLineCreate] = Field(default_factory=list, max_length=80)


class BudgetStarterRequest(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    scope: FinanceScope
    from_active_plan: bool = True


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
    horizon_days: int = Field(default=30, ge=7, le=365)
    entry_type: CashflowEntryType
    label: str = Field(min_length=1, max_length=128)
    amount_gbp: float
    is_confirmed: bool = False
    source: str = "manual"


class BudgetStyle(str, Enum):
    STABILISE = "stabilise"
    BALANCED = "balanced"
    DEBT_ATTACK = "debt_attack"
    CUSTOM = "custom"


class BudgetLineSource(str, Enum):
    RECURRING = "recurring"
    DEBT_MINIMUM = "debt_minimum"
    SNAPSHOT = "snapshot"
    SUGGESTED = "suggested"
    USER = "user"


class BudgetPlanLine(BaseModel):
    id: int | None = None
    scope: FinanceScope
    category: str
    amount_gbp: float
    source: str = "user"
    source_note: str = ""
    is_custom: bool = False
    sort_order: int = 0
    subcategory: str = ""
    basis_json: str = "{}"
    confidence: str = ""
    insufficient_data: bool = False


class BudgetPlanLineWrite(BaseModel):
    id: int | None = None
    scope: FinanceScope
    category: str = Field(min_length=1, max_length=64)
    amount_gbp: float = Field(ge=0)
    source: str = "user"
    source_note: str = ""
    is_custom: bool = False
    sort_order: int = 0
    subcategory: str = ""
    basis_json: str = "{}"
    confidence: str = ""
    insufficient_data: bool = False


class BudgetTotals(BaseModel):
    income_gbp: float = 0.0
    committed_gbp: float = 0.0
    total_spending_gbp: float = 0.0
    debt_payment_gbp: float = 0.0
    debt_overpayment_gbp: float = 0.0
    buffer_gbp: float = 0.0
    discretionary_gbp: float = 0.0
    tax_reserve_gbp: float = 0.0
    surplus_gbp: float = 0.0
    shortfall_gbp: float = 0.0


class BudgetGap(BaseModel):
    field: str
    message: str
    href: str = "/finance/personal"


class BudgetPlan(BaseModel):
    id: int
    name: str
    style: str
    origin: str
    notes: str = ""
    explanation: str = ""
    debt_intensity: str = "medium"
    cash_buffer_target_gbp: float = 0.0
    discretionary_gbp: float = 0.0
    tax_reserve_gbp: float = 0.0
    income_gbp: float = 0.0
    is_active: bool = False
    active_scope: str = ""
    totals: BudgetTotals = Field(default_factory=BudgetTotals)
    lines: list[BudgetPlanLine] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class BudgetPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    style: BudgetStyle = BudgetStyle.CUSTOM
    origin: str = "user"
    notes: str = ""
    explanation: str = ""
    debt_intensity: str = "medium"
    cash_buffer_target_gbp: float = Field(default=0, ge=0)
    discretionary_gbp: float = Field(default=0, ge=0)
    tax_reserve_gbp: float = Field(default=0, ge=0)
    income_gbp: float | None = None
    lines: list[BudgetPlanLineWrite] = Field(default_factory=list)
    active_scope: str = ""


class BudgetPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    notes: str | None = None
    explanation: str | None = None
    debt_intensity: str | None = None
    cash_buffer_target_gbp: float | None = Field(default=None, ge=0)
    discretionary_gbp: float | None = Field(default=None, ge=0)
    tax_reserve_gbp: float | None = Field(default=None, ge=0)
    income_gbp: float | None = Field(default=None, ge=0)
    lines: list[BudgetPlanLineWrite] | None = None


class BudgetPlanFromSuggestion(BaseModel):
    style: BudgetStyle
    name: str | None = Field(default=None, min_length=1, max_length=128)
    activate: bool = False


class BudgetPlanFromHistory(BaseModel):
    scope: FinanceScope
    name: str | None = Field(default=None, min_length=1, max_length=128)
    activate: bool = False


class SuggestedBudgetOption(BaseModel):
    style: str
    name: str
    explanation: str
    debt_intensity: str
    cash_buffer_target_gbp: float
    discretionary_gbp: float
    tax_reserve_gbp: float
    income_gbp: float
    committed_gbp: float
    debt_payment_gbp: float
    debt_overpayment_gbp: float
    surplus_gbp: float
    shortfall_gbp: float
    recommended: bool
    incomplete: bool
    gaps: list[BudgetGap] = Field(default_factory=list)
    lines: list[BudgetPlanLine] = Field(default_factory=list)
    notes: str = ""


class BudgetSuggestionsResponse(BaseModel):
    income_gbp: float
    personal_income_known: bool
    default_style: str
    options: list[SuggestedBudgetOption]
    gaps: list[BudgetGap] = Field(default_factory=list)


class BudgetCompareRow(BaseModel):
    id: int | None = None
    key: str
    name: str
    style: str
    monthly_total_gbp: float
    surplus_gbp: float
    debt_overpayment_gbp: float
    buffer_gbp: float
    discretionary_gbp: float
    tax_reserve_gbp: float
    shortfall_gbp: float
    is_active: bool = False


class BudgetCompareResponse(BaseModel):
    rows: list[BudgetCompareRow]
    income_gbp: float


class BudgetVsActualLine(BaseModel):
    scope: FinanceScope
    category: str
    budget_gbp: float
    actual_gbp: float | None = None
    variance_gbp: float | None = None
    percent_used: float | None = None
    missing_actual: bool = False
    forecast_gbp: float | None = None
    remaining_gbp: float | None = None
    actual_source: str = ""
    transaction_count: int = 0


class BudgetVsActualResponse(BaseModel):
    month: str
    plan_id: int | None = None
    plan_name: str | None = None
    lines: list[BudgetVsActualLine] = Field(default_factory=list)
    unbudgeted_actuals: list[BudgetVsActualLine] = Field(default_factory=list)
    has_actuals: bool = False
    available: bool = False
    reason: str = ""
    budgeted_total_gbp: float = 0.0
    actual_total_gbp: float = 0.0
    variance_total_gbp: float | None = None


class ActiveBudgetSummary(BaseModel):
    id: int
    name: str
    style: str
    monthly_total_gbp: float
    surplus_gbp: float
    debt_overpayment_gbp: float
    buffer_target_gbp: float
    income_gbp: float = 0.0


class DebtAnalysisItem(BaseModel):
    id: int
    name: str
    scope: str
    debt_type: str
    balance_gbp: float
    interest_rate_pct: float
    minimum_payment_gbp: float
    overpayment_gbp: float
    monthly_interest_gbp: float | None = None
    months_to_payoff: int | None = None
    priority_score: float
    priority_label: str
    apr_known: bool = True


class DebtScenarioResult(BaseModel):
    extra_gbp: float
    months_current: int | None = None
    months_with_extra: int | None = None
    months_saved: int | None = None
    interest_current_gbp: float | None = None
    interest_with_extra_gbp: float | None = None
    interest_saved_gbp: float | None = None
    payoff_date: str | None = None
    incomplete: bool = False
    reason: str = ""


class DebtStrategyRecommendation(BaseModel):
    strategy: str
    headline: str
    message: str
    debts: list[dict[str, Any]] = Field(default_factory=list)
    estimated_debt_free_date: str | None = None
    analysis: list[DebtAnalysisItem] = Field(default_factory=list)
    scenarios: list[DebtScenarioResult] = Field(default_factory=list)


class CashflowForecastEntryUpdate(BaseModel):
    forecast_date: str | None = None
    label: str | None = Field(default=None, min_length=1, max_length=128)
    amount_gbp: float | None = None
    is_confirmed: bool | None = None
    entry_type: CashflowEntryType | None = None


class FinanceInsight(BaseModel):
    id: int
    category: FinanceInsightCategory
    severity: FinanceInsightSeverity
    title: str
    message: str
    status: str
    related_date: str | None = None
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
    personal_credit_card_balances_gbp: float = 0.0
    loan_balances_gbp: float
    mortgage_balance_gbp: float
    pension_value_gbp: float
    directors_loan_gbp: float
    net_worth_estimate_gbp: float
    monthly_surplus_gbp: float
    available_cash_gbp: float = 0.0
    available_credit_gbp: float = 0.0
    credit_limit_gbp: float = 0.0
    personal_overdraft_gbp: float = 0.0
    business_overdraft_gbp: float = 0.0
    total_assets_gbp: float = 0.0
    property_gbp: float = 0.0
    month_budgeted_gbp: float = 0.0
    month_actual_gbp: float = 0.0
    active_budget: ActiveBudgetSummary | None = None
    insights: list[FinanceInsight] = Field(default_factory=list)
    personal_net_worth_gbp: float = 0.0
    company_position_gbp: float = 0.0
    director_owes_company_gbp: float = 0.0
    company_owes_director_gbp: float = 0.0
    external_debt_gbp: float = 0.0
    total_debt_gbp: float = 0.0
    cash_available_gbp: float = 0.0
    household_bills_gbp: float = 0.0
    monthly_flow_source: str = "none"
    monthly_interest_gbp: float = 0.0
    monthly_interest_incomplete: bool = False
    high_interest_debt_gbp: float = 0.0
    upcoming_payments: list[dict[str, Any]] = Field(default_factory=list)
    pension_configured: bool = False
    mortgage_configured: bool = False
    safe_to_spend: dict[str, Any] = Field(default_factory=dict)
    cash_status: str = "HEALTHY"
    generated_at: datetime | None = None
    cached: bool = False
    compute_ms: float | None = None
    quickfile_synced_at: str | None = None
    lunchflow_synced_at: str | None = None
    liquid_assets_gbp: float = 0.0
    long_term_assets_gbp: float = 0.0
    property_value_gbp: float = 0.0
    debtors_gbp: float = 0.0
    short_term_debt_gbp: float = 0.0
    long_term_debt_gbp: float = 0.0
    home_equity_gbp: float = 0.0
    personal_short_term_debt_gbp: float = 0.0
    personal_long_term_debt_gbp: float = 0.0
    business_short_term_debt_gbp: float = 0.0
    business_long_term_debt_gbp: float = 0.0


class CashflowScopeColumn(BaseModel):
    scope: FinanceScope
    starting_balance_gbp: float
    projected_balance_gbp: float
    entries: list[CashflowForecastEntry] = Field(default_factory=list)
    cash_pressure_warning: bool = False


class CashflowForecastResponse(BaseModel):
    horizon_days: int
    starting_balance_gbp: float
    projected_balance_gbp: float
    entries: list[CashflowForecastEntry]
    cash_pressure_warning: bool
    warning_message: str = ""
    columns: list[CashflowScopeColumn] = Field(default_factory=list)


class FinanceReportsResponse(BaseModel):
    month: str
    personal_snapshot: PersonalFinanceSnapshot | None = None
    business_snapshot: BusinessFinanceSnapshot | None = None
    net_worth_gbp: float | None = None
    total_debt_gbp: float | None = None
    debt_reduction_gbp: float | None = None
    energy_savings_gbp: float
    energy_savings_vs_forecast: str = ""
    debt_reduction_available: bool = False
    previous_month_debt_gbp: float | None = None
    cashflow_history: list[CashflowHistoryPoint] = Field(default_factory=list)
    debt_history: list[DebtHistoryPoint] = Field(default_factory=list)
    pl_history: list[PlHistoryPoint] = Field(default_factory=list)
    quickfile_reports: QuickFileReportsResponse | None = None
    active_budget: ActiveBudgetSummary | None = None
    budget_vs_actual: BudgetVsActualResponse | None = None
    personal_report: PersonalFinanceReport | None = None
    business_report: BusinessFinanceReport | None = None


class FinancePositionSnapshot(BaseModel):
    month: str
    total_debt_gbp: float
    personal_debt_gbp: float
    business_debt_gbp: float
    net_worth_gbp: float
    cash_available_gbp: float
    recorded_at: datetime


class DebtHistoryPoint(BaseModel):
    month: str
    total_debt_gbp: float


class CashflowHistoryPoint(BaseModel):
    month: str
    income_gbp: float
    spending_gbp: float
    surplus_gbp: float


class PlHistoryPoint(BaseModel):
    month: str
    turnover_gbp: float
    expenses_gbp: float
    profit_gbp: float


class ReportCategorySpend(BaseModel):
    category: str
    amount_gbp: float
    transaction_count: int = 0


class ReportExpenseLine(BaseModel):
    id: int
    posted_on: str
    description: str
    category: str
    amount_gbp: float
    account_name: str = ""


class ReportDebtLine(BaseModel):
    id: int
    name: str
    debt_type: str
    balance_gbp: float
    interest_rate_pct: float
    minimum_payment_gbp: float
    interest_rate_known: bool = True


class PersonalFinanceReport(BaseModel):
    month: str
    cash_gbp: float
    overdraft_gbp: float = 0.0
    debt_gbp: float
    pension_gbp: float
    property_gbp: float = 0.0
    net_worth_gbp: float
    income_gbp: float | None = None
    spending_gbp: float | None = None
    surplus_gbp: float | None = None
    household_bills_gbp: float | None = None
    debt_repayments_gbp: float | None = None
    flow_source: str = "none"
    flow_note: str = ""
    transaction_count: int = 0
    spending_by_category: list[ReportCategorySpend] = Field(default_factory=list)
    largest_expenses: list[ReportExpenseLine] = Field(default_factory=list)
    debts: list[ReportDebtLine] = Field(default_factory=list)
    previous_month_income_gbp: float | None = None
    previous_month_spending_gbp: float | None = None
    income_change_gbp: float | None = None
    spending_change_gbp: float | None = None
    empty_state: str | None = None


class BusinessFinanceReport(BaseModel):
    month: str
    cash_gbp: float
    overdraft_gbp: float = 0.0
    debt_gbp: float
    debtors_gbp: float = 0.0
    creditors_gbp: float = 0.0
    vat_reserve_gbp: float = 0.0
    corp_tax_reserve_gbp: float = 0.0
    directors_loan_gbp: float = 0.0
    company_owes_director_gbp: float = 0.0
    director_owes_company_gbp: float = 0.0
    company_position_gbp: float
    turnover_gbp: float | None = None
    expenses_gbp: float | None = None
    profit_gbp: float | None = None
    ytd_turnover_gbp: float | None = None
    ytd_expenses_gbp: float | None = None
    ytd_profit_gbp: float | None = None
    vat_liability_gbp: float | None = None
    pl_source: str = "none"
    pl_note: str = ""
    transaction_count: int = 0
    spending_by_category: list[ReportCategorySpend] = Field(default_factory=list)
    largest_expenses: list[ReportExpenseLine] = Field(default_factory=list)
    debts: list[ReportDebtLine] = Field(default_factory=list)
    empty_state: str | None = None


class QuickFileReportLine(BaseModel):
    nominal_code: str | None = None
    label: str
    amount_gbp: float


class QuickFileReportSection(BaseModel):
    key: str
    label: str
    lines: list[QuickFileReportLine] = Field(default_factory=list)
    subtotal_gbp: float | None = None
    subtotal_label: str | None = None
    is_total: bool = False


class QuickFileProfitAndLossSummary(BaseModel):
    from_date: str
    to_date: str
    turnover_gbp: float
    cost_of_sales_gbp: float
    expenses_gbp: float
    net_profit_gbp: float
    sections: list[QuickFileReportSection] = Field(default_factory=list)


class QuickFileBalanceSheetSummary(BaseModel):
    to_date: str
    fixed_assets_gbp: float
    current_assets_gbp: float
    current_liabilities_gbp: float
    long_term_liabilities_gbp: float
    capital_and_reserves_gbp: float
    debtors_gbp: float = 0.0
    creditors_gbp: float = 0.0
    vat_liability_gbp: float = 0.0
    sections: list[QuickFileReportSection] = Field(default_factory=list)


class QuickFileReportsResponse(BaseModel):
    synced_at: str | None = None
    profit_and_loss_month: QuickFileProfitAndLossSummary | None = None
    profit_and_loss_ytd: QuickFileProfitAndLossSummary | None = None
    balance_sheet: QuickFileBalanceSheetSummary | None = None


class QuickFileConfig(BaseModel):
    account_number: str = ""
    api_key: str = ""
    application_id: str = ""


class QuickFileConfigStatus(BaseModel):
    account_number: str = ""
    api_key_set: bool = False
    application_id: str = ""
    configured: bool = False
    last_sync_at: str | None = None
    budget_account_external_ids: list[str] = Field(default_factory=list)


class QuickFileBudgetAccountsUpdate(BaseModel):
    external_ids: list[str] = Field(default_factory=list)


class QuickFileSyncResult(BaseModel):
    accounts_synced: int
    debtors_gbp: float
    reports_synced: bool = False
    imported: int = 0
    duplicates: int = 0
    rejected: int = 0
    message: str


class TrueLayerConfig(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    environment: str = "sandbox"


class TrueLayerConfigStatus(BaseModel):
    client_id: str = ""
    client_secret_set: bool = False
    redirect_uri: str = ""
    environment: str = "sandbox"
    configured: bool = False
    connected: bool = False
    last_sync_at: str | None = None


class TrueLayerSyncResult(BaseModel):
    accounts_synced: int
    message: str
    funding_circle_imported: bool = False
    funding_circle_message: str = ""
    imported: int = 0
    duplicates: int = 0
    rejected: int = 0


class LunchFlowConfig(BaseModel):
    api_key: str = ""


class LunchFlowConfigStatus(BaseModel):
    api_key_set: bool = False
    configured: bool = False
    connected: bool = False
    last_sync_at: str | None = None
    provider: str = "lunchflow"


class LunchFlowSyncResult(BaseModel):
    accounts_synced: int
    message: str
    imported: int = 0
    duplicates: int = 0
    rejected: int = 0


class FinanceDailySyncResult(BaseModel):
    ok: bool = True
    quickfile: str = ""
    lunchflow: str = ""
    backup: str = ""


class TeslaConfig(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    energy_site_id: str = ""


class TeslaConfigStatus(BaseModel):
    client_id: str = ""
    client_secret_set: bool = False
    refresh_token_set: bool = False
    energy_site_id: str = ""
    configured: bool = False
    connected: bool = False
    last_sync_at: str | None = None


class FundingCircleConfig(BaseModel):
    outstanding_gbp: float | None = Field(default=None, ge=0)
    original_gbp: float | None = Field(default=None, ge=0)
    apr_pct: float = Field(default=0, ge=0, le=100)
    minimum_payment_gbp: float = Field(default=0, ge=0)
    payment_day: int | None = Field(default=None, ge=1, le=31)
    auto_sync: bool = True
    last_source: str = ""
    last_txn_on: str = ""
    message: str = ""


class FundingCircleConfigStatus(BaseModel):
    configured: bool = False
    auto_sync: bool = True
    outstanding_gbp: float | None = None
    original_gbp: float | None = None
    apr_pct: float = 0
    minimum_payment_gbp: float = 0
    payment_day: int | None = None
    last_sync_at: str | None = None
    last_source: str = ""
    last_txn_on: str = ""
    message: str = ""


class FundingCircleSyncResult(BaseModel):
    imported: bool
    balance_gbp: float
    repayments_applied_gbp: float
    source: str
    message: str


class TeslaChargingStatus(BaseModel):
    connected: bool
    vehicle_name: str = ""
    charging_state: str = ""
    battery_level_pct: float | None = None
    charge_limit_pct: float | None = None
    charger_power_kw: float | None = None
    energy_site_id: str = ""
    message: str = ""
