"""Finance domain schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class FinanceScope(str, Enum):
    PERSONAL = "personal"
    BUSINESS = "business"


class FinanceAccountType(str, Enum):
    CURRENT = "current"
    CREDIT_CARD = "credit_card"
    LOAN = "loan"
    MORTGAGE = "mortgage"
    PROPERTY = "property"
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
    LUNCH_FLOW = "lunch_flow"


def account_is_historic(source: FinanceAccountSource) -> bool:
    """True when balance is manually entered rather than synced live."""
    return source not in (
        FinanceAccountSource.QUICKFILE,
        FinanceAccountSource.OPEN_BANKING,
        FinanceAccountSource.LUNCH_FLOW,
    )


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
    credit_limit_gbp: float | None = None
    interest_rate_pct: float | None = None
    minimum_payment_gbp: float | None = None
    notes: str = ""
    source: FinanceAccountSource = FinanceAccountSource.MANUAL
    external_id: str | None = None
    is_active: bool = True
    is_historic: bool = False
    data_confidence: str = "manual"
    last_synced_at: datetime | None = None
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


class FinanceAccountUpdate(BaseModel):
    name: str | None = None
    account_type: FinanceAccountType | None = None
    provider: str | None = None
    balance_gbp: float | None = None
    credit_limit_gbp: float | None = None
    interest_rate_pct: float | None = None
    minimum_payment_gbp: float | None = None
    notes: str | None = None
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
    payment_day: int | None = None
    account_id: int | None = None
    notes: str = ""
    is_active: bool = True
    is_historic: bool = False
    data_confidence: str = "manual"
    last_synced_at: datetime | None = None
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
    payment_day: int | None = Field(default=None, ge=1, le=31)
    account_id: int | None = None
    notes: str = ""


class FinanceLiabilityUpdate(BaseModel):
    name: str | None = None
    balance_gbp: float | None = Field(default=None, ge=0)
    interest_rate_pct: float | None = Field(default=None, ge=0, le=100)
    minimum_payment_gbp: float | None = Field(default=None, ge=0)
    overpayment_gbp: float | None = Field(default=None, ge=0)
    payment_day: int | None = Field(default=None, ge=1, le=31)
    notes: str | None = None
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
    budgeted_gbp: float | None = Field(default=None, ge=0)
    actual_gbp: float | None = Field(default=None, ge=0)
    notes: str | None = None


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
    loan_balances_gbp: float
    mortgage_balance_gbp: float
    pension_value_gbp: float
    directors_loan_gbp: float
    liquid_assets_gbp: float = 0.0
    long_term_assets_gbp: float = 0.0
    property_value_gbp: float = 0.0
    debtors_gbp: float = 0.0
    total_assets_gbp: float = 0.0
    short_term_debt_gbp: float = 0.0
    long_term_debt_gbp: float = 0.0
    total_debt_gbp: float = 0.0
    home_equity_gbp: float = 0.0
    personal_short_term_debt_gbp: float = 0.0
    personal_long_term_debt_gbp: float = 0.0
    business_short_term_debt_gbp: float = 0.0
    business_long_term_debt_gbp: float = 0.0
    net_worth_estimate_gbp: float
    monthly_surplus_gbp: float
    personal_monthly_income_gbp: float = 0.0
    business_monthly_turnover_gbp: float = 0.0
    business_monthly_expenses_gbp: float = 0.0
    business_monthly_net_profit_gbp: float = 0.0
    business_ytd_turnover_gbp: float = 0.0
    business_ytd_net_profit_gbp: float = 0.0
    business_income_from_quickfile: bool = False
    quickfile_reports_at: str | None = None
    historic_fields: list[str] = Field(default_factory=list)
    insights: list[FinanceInsight] = Field(default_factory=list)


class HistoricFinanceSeedResponse(BaseModel):
    accounts_created: int
    liabilities_created: int
    snapshot_created: bool
    skipped: bool
    message: str


class DebtStrategyRecommendation(BaseModel):
    strategy: str
    headline: str
    message: str
    debts: list[dict[str, Any]] = Field(default_factory=list)
    estimated_debt_free_date: str | None = None


class CashflowForecastResponse(BaseModel):
    scope: FinanceScope
    horizon_days: int
    starting_balance_gbp: float
    projected_balance_gbp: float
    entries: list[CashflowForecastEntry]
    cash_pressure_warning: bool
    warning_message: str = ""
    is_stub: bool = False
    stub_message: str = ""


class CashflowForecastsResponse(BaseModel):
    horizon_days: int
    personal: CashflowForecastResponse
    business: CashflowForecastResponse


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


class FinanceReportsResponse(BaseModel):
    month: str
    personal_snapshot: PersonalFinanceSnapshot | None = None
    business_snapshot: BusinessFinanceSnapshot | None = None
    quickfile_reports: QuickFileReportsResponse | None = None
    net_worth_gbp: float
    total_debt_gbp: float
    debt_reduction_gbp: float
    energy_savings_gbp: float
    energy_savings_vs_forecast: str = ""


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


class QuickFileSyncResult(BaseModel):
    accounts_synced: int
    debtors_gbp: float
    reports_synced: bool = False
    message: str


class LunchFlowConfig(BaseModel):
    api_key: str = ""


class LunchFlowConfigStatus(BaseModel):
    api_key_set: bool = False
    configured: bool = False
    last_sync_at: str | None = None


class LunchFlowSyncResult(BaseModel):
    accounts_synced: int
    transactions_synced: int = 0
    message: str


class OpenBankingConfig(BaseModel):
    provider: Literal["enable_banking", "gocardless"] = "enable_banking"
    application_id: str = ""
    private_key_pem: str = ""
    environment: Literal["SANDBOX", "PRODUCTION"] = "SANDBOX"
    secret_id: str = ""
    secret_key: str = ""
    redirect_url: str = ""
    country: str = "gb"
    scopes: str = "accounts,transactions"
    webhook_url: str = ""
    access_token: str = ""
    refresh_token: str = ""
    access_expires_at: datetime | None = None


class OpenBankingRequisition(BaseModel):
    id: str
    institution_id: str
    institution_name: str
    status: str = "CR"
    account_ids: list[str] = Field(default_factory=list)
    reference: str = ""
    state: str = ""
    provider: Literal["enable_banking", "gocardless"] = "enable_banking"
    created_at: datetime | None = None


OpenBankingTestStatus = Literal[
    "connected_successfully",
    "missing_credentials",
    "invalid_redirect_url",
    "provider_rejected_credentials",
    "further_bank_authorisation_required",
]


class OpenBankingConfigStatus(BaseModel):
    provider: Literal["enable_banking", "gocardless"] = "enable_banking"
    application_id: str = ""
    private_key_set: bool = False
    environment: Literal["SANDBOX", "PRODUCTION"] = "SANDBOX"
    secret_id: str = ""
    secret_key_set: bool = False
    redirect_url: str = ""
    country: str = "gb"
    scopes: str = "accounts,transactions"
    webhook_url: str = ""
    configured: bool = False
    provider_ready: bool | None = None
    readiness_message: str | None = None
    readiness_status: OpenBankingTestStatus | None = None
    linked_banks: list[str] = Field(default_factory=list)
    connections_count: int = 0
    last_sync_at: str | None = None


OpenBankingSetupProvider = Literal["enable_banking", "gocardless"]
OpenBankingSetupEnvironment = Literal["sandbox", "live"]


class OpenBankingSetupSaveRequest(BaseModel):
    """Plain-English setup form payload from the UI."""

    provider: OpenBankingSetupProvider = "enable_banking"
    client_id: str = ""
    client_secret: str = ""
    redirect_url: str = ""
    environment: OpenBankingSetupEnvironment = "sandbox"
    country: str = Field(default="gb", min_length=2, max_length=2)
    scopes: str = "accounts,transactions"
    webhook_url: str = ""


class OpenBankingTestResult(BaseModel):
    status: OpenBankingTestStatus
    message: str
    details: dict[str, str] = Field(default_factory=dict)


class OpenBankingInstitution(BaseModel):
    id: str
    name: str
    logo: str = ""


class OpenBankingConnectRequest(BaseModel):
    institution_id: str = Field(min_length=2, max_length=128)
    institution_name: str = Field(min_length=2, max_length=128)


class OpenBankingConnectResponse(BaseModel):
    link: str
    requisition_id: str
    institution_id: str
    institution_name: str
    reference: str
    state: str = ""


class OpenBankingFinalizeRequest(BaseModel):
    reference: str | None = Field(default=None, min_length=8, max_length=128)
    state: str | None = Field(default=None, min_length=8, max_length=128)
    code: str | None = Field(default=None, min_length=4, max_length=512)


class OpenBankingSyncResult(BaseModel):
    accounts_synced: int
    message: str


class FinanceAiFinding(BaseModel):
    title: str
    detail: str
    severity: str = "info"


class FinanceAiAssessment(BaseModel):
    summary: str
    findings: list[FinanceAiFinding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    questions_you_might_ask: list[str] = Field(default_factory=list)


class FinanceAiChatMessage(BaseModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class FinanceAiChatRequest(BaseModel):
    messages: list[FinanceAiChatMessage] = Field(min_length=1, max_length=20)


class FinanceAiChatResponse(BaseModel):
    reply: str


class FinanceAiStatusResponse(BaseModel):
    enabled: bool
    model: str = ""
    reason: str = ""


class BankConnectionMethod(str, Enum):
    OPEN_BANKING = "open_banking"
    QUICKFILE = "quickfile"
    MANUAL = "manual"


class BankConnectionStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    NOT_CONNECTED = "not_connected"
    AWAITING_LOGIN = "awaiting_login"
    CONNECTED = "connected"
    NEEDS_RECONNECTION = "needs_reconnection"
    SYNC_FAILED = "sync_failed"
    MANUAL = "manual"


class FinanceDailySyncResult(BaseModel):
    open_banking: str = ""
    lunch_flow: str = ""
    quickfile: str = ""
    ok: bool = True


class BankConnectionItem(BaseModel):
    id: str
    label: str
    method: BankConnectionMethod
    status: BankConnectionStatus
    status_message: str
    last_sync_at: str | None = None
    institution: str = ""
    account_count: int = 0
    balance_gbp: float = 0.0


class BankConnectionsResponse(BaseModel):
    connections: list[BankConnectionItem] = Field(default_factory=list)


class FinanceTransaction(BaseModel):
    id: int
    account_id: int
    external_id: str
    transaction_date: str
    description: str = ""
    merchant: str = ""
    amount_gbp: float
    category: str = ""
    reference: str = ""
    is_pending: bool = False
    synced_at: datetime
    created_at: datetime
