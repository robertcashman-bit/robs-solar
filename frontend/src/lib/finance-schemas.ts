import { z } from "zod";

export const financeScopeSchema = z.enum(["personal", "business"]);

export const financeAccountTypeSchema = z.enum([
  "current",
  "credit_card",
  "loan",
  "mortgage",
  "property",
  "pension",
  "directors_loan",
  "vat_reserve",
  "corp_tax_reserve",
  "capital_on_tap",
  "debtors",
  "creditors",
  "other",
]);

export const financeInsightSchema = z.object({
  id: z.number(),
  category: z.enum(["cashflow", "debt", "tax", "business", "energy"]),
  severity: z.enum(["info", "warning", "critical"]),
  title: z.string(),
  message: z.string(),
  status: z.string(),
  related_date: z.string().nullable().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
  created_at: z.string(),
});

export const financeOverviewSchema = z.object({
  personal_bank_balance_gbp: z.number(),
  business_bank_balance_gbp: z.number(),
  total_personal_debt_gbp: z.number(),
  total_business_debt_gbp: z.number(),
  monthly_income_gbp: z.number(),
  monthly_spending_gbp: z.number(),
  cash_after_bills_gbp: z.number(),
  vat_reserve_gbp: z.number(),
  corp_tax_reserve_gbp: z.number(),
  vat_reserve_warning: z.boolean(),
  corp_tax_reserve_warning: z.boolean(),
  credit_card_balances_gbp: z.number(),
  loan_balances_gbp: z.number(),
  mortgage_balance_gbp: z.number(),
  pension_value_gbp: z.number(),
  directors_loan_gbp: z.number(),
  liquid_assets_gbp: z.number(),
  long_term_assets_gbp: z.number(),
  property_value_gbp: z.number(),
  debtors_gbp: z.number(),
  total_assets_gbp: z.number(),
  short_term_debt_gbp: z.number(),
  long_term_debt_gbp: z.number(),
  total_debt_gbp: z.number(),
  home_equity_gbp: z.number(),
  personal_short_term_debt_gbp: z.number(),
  personal_long_term_debt_gbp: z.number(),
  business_short_term_debt_gbp: z.number(),
  business_long_term_debt_gbp: z.number(),
  net_worth_estimate_gbp: z.number(),
  monthly_surplus_gbp: z.number(),
  personal_monthly_income_gbp: z.number().default(0),
  business_monthly_turnover_gbp: z.number().default(0),
  business_monthly_expenses_gbp: z.number().default(0),
  business_monthly_net_profit_gbp: z.number().default(0),
  business_ytd_turnover_gbp: z.number().default(0),
  business_ytd_net_profit_gbp: z.number().default(0),
  business_income_from_quickfile: z.boolean().default(false),
  quickfile_reports_at: z.string().nullable().optional(),
  historic_fields: z.array(z.string()).default([]),
  insights: z.array(financeInsightSchema),
});

export const financeAccountSchema = z.object({
  id: z.number(),
  scope: financeScopeSchema,
  account_type: financeAccountTypeSchema,
  name: z.string(),
  provider: z.string(),
  balance_gbp: z.number(),
  credit_limit_gbp: z.number().nullable().optional(),
  interest_rate_pct: z.number().nullable().optional(),
  minimum_payment_gbp: z.number().nullable().optional(),
  notes: z.string(),
  source: z.string(),
  external_id: z.string().nullable().optional(),
  is_active: z.boolean(),
  is_historic: z.boolean().default(false),
  created_at: z.string(),
  updated_at: z.string(),
});

export const financeLiabilitySchema = z.object({
  id: z.number(),
  scope: financeScopeSchema,
  name: z.string(),
  debt_type: z.string(),
  balance_gbp: z.number(),
  interest_rate_pct: z.number(),
  minimum_payment_gbp: z.number(),
  overpayment_gbp: z.number(),
  payment_day: z.number().nullable().optional(),
  account_id: z.number().nullable().optional(),
  notes: z.string(),
  is_active: z.boolean(),
  is_historic: z.boolean().default(true),
  created_at: z.string(),
  updated_at: z.string(),
});

export const personalFinanceSnapshotSchema = z.object({
  id: z.number(),
  snapshot_date: z.string(),
  monthly_income_gbp: z.number(),
  monthly_spending_gbp: z.number(),
  household_bills_gbp: z.number(),
  debt_repayments_gbp: z.number(),
  surplus_deficit_gbp: z.number(),
  notes: z.string(),
  breakdown: z.record(z.string(), z.unknown()).optional(),
  created_at: z.string(),
});

export const businessFinanceSnapshotSchema = z.object({
  id: z.number(),
  snapshot_date: z.string(),
  turnover_gbp: z.number(),
  expenses_gbp: z.number(),
  vat_reserve_gbp: z.number(),
  corp_tax_reserve_gbp: z.number(),
  debtors_gbp: z.number(),
  creditors_gbp: z.number(),
  profit_estimate_gbp: z.number(),
  cash_available_to_draw_gbp: z.number(),
  notes: z.string(),
  breakdown: z.record(z.string(), z.unknown()).optional(),
  created_at: z.string(),
});

export const monthlyBudgetLineSchema = z.object({
  id: z.number(),
  scope: financeScopeSchema,
  month: z.string(),
  category: z.string(),
  budgeted_gbp: z.number(),
  actual_gbp: z.number(),
  remaining_gbp: z.number(),
  notes: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const cashflowForecastEntrySchema = z.object({
  id: z.number(),
  scope: financeScopeSchema,
  forecast_date: z.string(),
  horizon_days: z.number(),
  entry_type: z.enum(["income", "bill", "debt", "tax_vat", "other"]),
  label: z.string(),
  amount_gbp: z.number(),
  is_confirmed: z.boolean(),
  source: z.string(),
  created_at: z.string(),
});

export const cashflowForecastSchema = z.object({
  scope: financeScopeSchema,
  horizon_days: z.number(),
  starting_balance_gbp: z.number(),
  projected_balance_gbp: z.number(),
  entries: z.array(cashflowForecastEntrySchema),
  cash_pressure_warning: z.boolean(),
  warning_message: z.string(),
});

export const cashflowForecastsSchema = z.object({
  horizon_days: z.number(),
  personal: cashflowForecastSchema,
  business: cashflowForecastSchema,
});

export const debtStrategySchema = z.object({
  strategy: z.string(),
  headline: z.string(),
  message: z.string(),
  debts: z.array(z.record(z.string(), z.unknown())),
  estimated_debt_free_date: z.string().nullable().optional(),
});

export const quickFileReportLineSchema = z.object({
  nominal_code: z.string().nullable().optional(),
  label: z.string(),
  amount_gbp: z.number(),
});

export const quickFileReportSectionSchema = z.object({
  key: z.string(),
  label: z.string(),
  lines: z.array(quickFileReportLineSchema).default([]),
  subtotal_gbp: z.number().nullable().optional(),
  subtotal_label: z.string().nullable().optional(),
  is_total: z.boolean().default(false),
});

export const quickFileProfitAndLossSummarySchema = z.object({
  from_date: z.string(),
  to_date: z.string(),
  turnover_gbp: z.number(),
  cost_of_sales_gbp: z.number(),
  expenses_gbp: z.number(),
  net_profit_gbp: z.number(),
  sections: z.array(quickFileReportSectionSchema).default([]),
});

export const quickFileBalanceSheetSummarySchema = z.object({
  to_date: z.string(),
  fixed_assets_gbp: z.number(),
  current_assets_gbp: z.number(),
  current_liabilities_gbp: z.number(),
  long_term_liabilities_gbp: z.number(),
  capital_and_reserves_gbp: z.number(),
  debtors_gbp: z.number().default(0),
  creditors_gbp: z.number().default(0),
  vat_liability_gbp: z.number().default(0),
  sections: z.array(quickFileReportSectionSchema).default([]),
});

export const quickFileReportsSchema = z.object({
  synced_at: z.string().nullable().optional(),
  profit_and_loss_month: quickFileProfitAndLossSummarySchema.nullable().optional(),
  profit_and_loss_ytd: quickFileProfitAndLossSummarySchema.nullable().optional(),
  balance_sheet: quickFileBalanceSheetSummarySchema.nullable().optional(),
});

export const financeReportsSchema = z.object({
  month: z.string(),
  personal_snapshot: personalFinanceSnapshotSchema.nullable().optional(),
  business_snapshot: businessFinanceSnapshotSchema.nullable().optional(),
  quickfile_reports: quickFileReportsSchema.nullable().optional(),
  net_worth_gbp: z.number(),
  total_debt_gbp: z.number(),
  debt_reduction_gbp: z.number(),
  energy_savings_gbp: z.number(),
  energy_savings_vs_forecast: z.string(),
});

export const quickFileConfigStatusSchema = z.object({
  account_number: z.string(),
  api_key_set: z.boolean(),
  application_id: z.string(),
  configured: z.boolean(),
  last_sync_at: z.string().nullable().optional(),
});

export const quickFileSyncResultSchema = z.object({
  accounts_synced: z.number(),
  debtors_gbp: z.number(),
  reports_synced: z.boolean().optional(),
  message: z.string(),
});

export const openBankingConfigStatusSchema = z.object({
  provider: z.enum(["enable_banking", "gocardless"]).default("enable_banking"),
  application_id: z.string(),
  private_key_set: z.boolean(),
  environment: z.enum(["SANDBOX", "PRODUCTION"]).default("SANDBOX"),
  secret_id: z.string(),
  secret_key_set: z.boolean(),
  redirect_url: z.string(),
  country: z.string().default("gb"),
  scopes: z.string().default("accounts,transactions"),
  webhook_url: z.string().default(""),
  configured: z.boolean(),
  provider_ready: z.boolean().nullable().optional(),
  readiness_message: z.string().nullable().optional(),
  readiness_status: z
    .enum([
      "connected_successfully",
      "missing_credentials",
      "invalid_redirect_url",
      "provider_rejected_credentials",
      "further_bank_authorisation_required",
    ])
    .nullable()
    .optional(),
  linked_banks: z.array(z.string()),
  connections_count: z.number(),
  last_sync_at: z.string().nullable().optional(),
});

export const openBankingTestResultSchema = z.object({
  status: z.enum([
    "connected_successfully",
    "missing_credentials",
    "invalid_redirect_url",
    "provider_rejected_credentials",
    "further_bank_authorisation_required",
  ]),
  message: z.string(),
  details: z.record(z.string(), z.string()).default({}),
});

export const openBankingSetupSaveSchema = z.object({
  provider: z.enum(["enable_banking", "gocardless"]),
  client_id: z.string().min(1, "Client ID is required"),
  client_secret: z.string(),
  redirect_url: z.string().min(1, "Redirect URL is required"),
  environment: z.enum(["sandbox", "live"]),
  country: z.string().length(2, "Bank country must be a two-letter code"),
  scopes: z.string().min(1, "Scopes are required"),
  webhook_url: z.string(),
});

export const openBankingInstitutionSchema = z.object({
  id: z.string(),
  name: z.string(),
  logo: z.string().optional(),
});

export const openBankingConnectResponseSchema = z.object({
  link: z.string(),
  requisition_id: z.string(),
  institution_id: z.string(),
  institution_name: z.string(),
  reference: z.string(),
  state: z.string().optional(),
});

export const openBankingSyncResultSchema = z.object({
  accounts_synced: z.number(),
  message: z.string(),
});

export const financeAiFindingSchema = z.object({
  title: z.string(),
  detail: z.string(),
  severity: z.enum(["info", "warning", "critical"]).default("info"),
});

export const financeAiAssessmentSchema = z.object({
  summary: z.string(),
  findings: z.array(financeAiFindingSchema),
  recommendations: z.array(z.string()),
  questions_you_might_ask: z.array(z.string()),
});

export const financeAiStatusSchema = z.object({
  enabled: z.boolean(),
  model: z.string(),
  reason: z.string(),
});

export const financeAiChatMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string(),
});

export const financeAiChatResponseSchema = z.object({
  reply: z.string(),
});

export type QuickFileReportLine = z.infer<typeof quickFileReportLineSchema>;
export type QuickFileReportSection = z.infer<typeof quickFileReportSectionSchema>;
export type QuickFileProfitAndLossSummary = z.infer<typeof quickFileProfitAndLossSummarySchema>;
export type QuickFileBalanceSheetSummary = z.infer<typeof quickFileBalanceSheetSummarySchema>;
export type QuickFileReports = z.infer<typeof quickFileReportsSchema>;
export type QuickFileConfigStatus = z.infer<typeof quickFileConfigStatusSchema>;
export type QuickFileSyncResult = z.infer<typeof quickFileSyncResultSchema>;
export type OpenBankingConfigStatus = z.infer<typeof openBankingConfigStatusSchema>;
export type OpenBankingTestResult = z.infer<typeof openBankingTestResultSchema>;
export type OpenBankingSetupSave = z.infer<typeof openBankingSetupSaveSchema>;
export type OpenBankingInstitution = z.infer<typeof openBankingInstitutionSchema>;
export type OpenBankingConnectResponse = z.infer<typeof openBankingConnectResponseSchema>;
export type OpenBankingSyncResult = z.infer<typeof openBankingSyncResultSchema>;

export const bankConnectionStatusSchema = z.enum([
  "not_configured",
  "not_connected",
  "awaiting_login",
  "connected",
  "needs_reconnection",
  "sync_failed",
  "manual",
]);

export const bankConnectionMethodSchema = z.enum(["open_banking", "quickfile", "manual"]);

export const bankConnectionItemSchema = z.object({
  id: z.string(),
  label: z.string(),
  method: bankConnectionMethodSchema,
  status: bankConnectionStatusSchema,
  status_message: z.string(),
  last_sync_at: z.string().nullable().optional(),
  institution: z.string().optional(),
  account_count: z.number(),
  balance_gbp: z.number(),
});

export const bankConnectionsResponseSchema = z.object({
  connections: z.array(bankConnectionItemSchema),
});

export const financeTransactionSchema = z.object({
  id: z.number(),
  account_id: z.number(),
  external_id: z.string(),
  transaction_date: z.string(),
  description: z.string(),
  merchant: z.string(),
  amount_gbp: z.number(),
  category: z.string(),
  reference: z.string(),
  is_pending: z.boolean(),
  synced_at: z.string(),
  created_at: z.string(),
});

export type BankConnectionItem = z.infer<typeof bankConnectionItemSchema>;
export type FinanceTransaction = z.infer<typeof financeTransactionSchema>;
export type FinanceAiAssessment = z.infer<typeof financeAiAssessmentSchema>;
export type FinanceAiStatus = z.infer<typeof financeAiStatusSchema>;
export type FinanceAiChatMessage = z.infer<typeof financeAiChatMessageSchema>;

export type FinanceOverview = z.infer<typeof financeOverviewSchema>;
export type FinanceAccount = z.infer<typeof financeAccountSchema>;
export type FinanceLiability = z.infer<typeof financeLiabilitySchema>;
export type FinanceInsight = z.infer<typeof financeInsightSchema>;
export type PersonalFinanceSnapshot = z.infer<typeof personalFinanceSnapshotSchema>;
export type BusinessFinanceSnapshot = z.infer<typeof businessFinanceSnapshotSchema>;
export type MonthlyBudgetLine = z.infer<typeof monthlyBudgetLineSchema>;
export type CashflowForecast = z.infer<typeof cashflowForecastSchema>;
export type DebtStrategy = z.infer<typeof debtStrategySchema>;
export type FinanceReports = z.infer<typeof financeReportsSchema>;
