import { z } from "zod";

export const financeScopeSchema = z.enum(["personal", "business"]);

export const activeBudgetSummarySchema = z.object({
  id: z.number(),
  name: z.string(),
  style: z.string(),
  monthly_total_gbp: z.number(),
  surplus_gbp: z.number(),
  debt_overpayment_gbp: z.number(),
  buffer_target_gbp: z.number(),
  income_gbp: z.number().optional().default(0),
});

export const financeAccountTypeSchema = z.enum([
  "current",
  "credit_card",
  "loan",
  "mortgage",
  "pension",
  "directors_loan",
  "vat_reserve",
  "corp_tax_reserve",
  "capital_on_tap",
  "debtors",
  "creditors",
  "property",
  "other_asset",
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

export const periodFlowSummarySchema = z.object({
  period: z.string(),
  scope: z.string(),
  label: z.string(),
  date_from: z.string(),
  date_to: z.string(),
  months_requested: z.number().optional().default(1),
  months_with_data: z.number().optional().default(0),
  transaction_count: z.number().optional().default(0),
  income_gbp: z.number().optional().default(0),
  spending_gbp: z.number().optional().default(0),
  surplus_gbp: z.number().optional().default(0),
  history_partial: z.boolean().optional().default(false),
  coverage_note: z.string().optional().default(""),
  source: z.string().optional().default("transactions"),
  money_in_label: z.string().optional().default("Money in"),
  money_out_label: z.string().optional().default("Money out"),
});

export const overviewLineItemSchema = z.object({
  key: z.string(),
  label: z.string(),
  amount_gbp: z.number().nullable().optional(),
  kind: z.string().optional().default("asset"),
  tier: z.string().optional().default("primary"),
  hint: z.string().optional().default(""),
});

export const overviewSideBreakdownSchema = z.object({
  side: z.string(),
  owned_total_gbp: z.number().optional().default(0),
  owed_total_gbp: z.number().optional().default(0),
  whats_left_gbp: z.number().optional().default(0),
  owned: z.array(overviewLineItemSchema).optional().default([]),
  owed: z.array(overviewLineItemSchema).optional().default([]),
});

export const financeDataGapsSchema = z.object({
  unknown_apr_count: z.number().optional().default(0),
  unknown_apr_names: z.array(z.string()).optional().default([]),
  missing_credit_limit_count: z.number().optional().default(0),
  missing_credit_limit_names: z.array(z.string()).optional().default([]),
  monthly_interest_incomplete: z.boolean().optional().default(false),
  income_looks_thin: z.boolean().optional().default(false),
  income_thin_note: z.string().optional().default(""),
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
  personal_credit_card_balances_gbp: z.number().optional().default(0),
  business_credit_card_balances_gbp: z.number().optional().default(0),
  loan_balances_gbp: z.number(),
  personal_loan_balances_gbp: z.number().optional().default(0),
  mortgage_balance_gbp: z.number(),
  pension_value_gbp: z.number(),
  directors_loan_gbp: z.number(),
  net_worth_estimate_gbp: z.number(),
  monthly_surplus_gbp: z.number(),
  available_cash_gbp: z.number().optional().default(0),
  available_credit_gbp: z.number().optional().default(0),
  credit_limit_gbp: z.number().optional().default(0),
  personal_overdraft_gbp: z.number().optional().default(0),
  business_overdraft_gbp: z.number().optional().default(0),
  total_assets_gbp: z.number().optional().default(0),
  property_gbp: z.number().optional().default(0),
  month_budgeted_gbp: z.number().optional().default(0),
  month_actual_gbp: z.number().optional().default(0),
  personal_net_worth_gbp: z.number().optional().default(0),
  company_position_gbp: z.number().optional().default(0),
  director_owes_company_gbp: z.number().optional().default(0),
  company_owes_director_gbp: z.number().optional().default(0),
  external_debt_gbp: z.number().optional().default(0),
  total_debt_gbp: z.number().optional().default(0),
  cash_available_gbp: z.number().optional().default(0),
  household_bills_gbp: z.number().optional().default(0),
  monthly_flow_source: z.string().optional().default("none"),
  monthly_interest_gbp: z.number().optional().default(0),
  monthly_interest_incomplete: z.boolean().optional().default(false),
  high_interest_debt_gbp: z.number().optional().default(0),
  upcoming_payments: z
    .array(
      z.object({
        name: z.string(),
        scope: z.string(),
        amount_gbp: z.number(),
        due_date: z.string(),
        days_until: z.number(),
      }),
    )
    .optional()
    .default([]),
  pension_configured: z.boolean().optional(),
  mortgage_configured: z.boolean().optional(),
  safe_to_spend: z
    .object({
      personal: z
        .object({
          safe_to_spend_gbp: z.number(),
          status: z.string(),
          flow_source: z.string().optional(),
          flow_note: z.string().optional(),
          breakdown: z.record(z.string(), z.unknown()).optional(),
        })
        .optional(),
      business: z
        .object({
          available_business_cash_gbp: z.number(),
          status: z.string(),
          breakdown: z.record(z.string(), z.unknown()).optional(),
        })
        .optional(),
      combined: z
        .object({
          safe_to_spend_gbp: z.number(),
          status: z.string(),
          flow_source: z.string().optional(),
          flow_note: z.string().optional(),
        })
        .optional(),
    })
    .optional()
    .default({}),
  cash_status: z.string().optional().default("HEALTHY"),
  generated_at: z.string().nullable().optional(),
  cached: z.boolean().optional().default(false),
  compute_ms: z.number().nullable().optional(),
  quickfile_synced_at: z.string().nullable().optional(),
  lunchflow_synced_at: z.string().nullable().optional(),
  liquid_assets_gbp: z.number().optional().default(0),
  long_term_assets_gbp: z.number().optional().default(0),
  property_value_gbp: z.number().optional().default(0),
  debtors_gbp: z.number().optional().default(0),
  short_term_debt_gbp: z.number().optional().default(0),
  long_term_debt_gbp: z.number().optional().default(0),
  home_equity_gbp: z.number().optional().default(0),
  personal_short_term_debt_gbp: z.number().optional().default(0),
  personal_long_term_debt_gbp: z.number().optional().default(0),
  business_short_term_debt_gbp: z.number().optional().default(0),
  business_long_term_debt_gbp: z.number().optional().default(0),
  personal_period_flow: periodFlowSummarySchema.nullable().optional(),
  business_period_flow: periodFlowSummarySchema.nullable().optional(),
  personal_breakdown: overviewSideBreakdownSchema.nullable().optional(),
  business_breakdown: overviewSideBreakdownSchema.nullable().optional(),
  data_gaps: financeDataGapsSchema.optional(),
  active_budget: activeBudgetSummarySchema.nullable().optional(),
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
  dla_direction: z.enum(["director_owes_company", "company_owes_director"]).nullable().optional(),
  is_active: z.boolean(),
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
  original_balance_gbp: z.number().nullable().optional(),
  payment_day: z.number().nullable().optional(),
  account_id: z.number().nullable().optional(),
  notes: z.string(),
  dla_direction: z.enum(["director_owes_company", "company_owes_director"]).nullable().optional(),
  interest_rate_known: z.boolean().optional().default(true),
  credit_limit_gbp: z.number().nullable().optional(),
  is_active: z.boolean(),
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
  actual_gbp: z.number().nullable().optional(),
  remaining_gbp: z.number().nullable().optional(),
  actual_recorded: z.boolean().optional().default(false),
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

export const cashflowScopeColumnSchema = z.object({
  scope: financeScopeSchema,
  starting_balance_gbp: z.number(),
  projected_balance_gbp: z.number(),
  entries: z.array(cashflowForecastEntrySchema).optional().default([]),
  cash_pressure_warning: z.boolean().optional().default(false),
});

export const cashflowForecastSchema = z.object({
  horizon_days: z.number(),
  starting_balance_gbp: z.number(),
  projected_balance_gbp: z.number(),
  entries: z.array(cashflowForecastEntrySchema),
  cash_pressure_warning: z.boolean(),
  warning_message: z.string(),
  columns: z.array(cashflowScopeColumnSchema).optional().default([]),
});

export const debtAnalysisItemSchema = z.object({
  id: z.number(),
  name: z.string(),
  scope: z.string(),
  debt_type: z.string(),
  balance_gbp: z.number(),
  interest_rate_pct: z.number(),
  minimum_payment_gbp: z.number(),
  overpayment_gbp: z.number(),
  monthly_interest_gbp: z.number().nullable().optional(),
  months_to_payoff: z.number().nullable().optional(),
  priority_score: z.number(),
  priority_label: z.string(),
  apr_known: z.boolean().optional(),
});

export const debtScenarioSchema = z.object({
  extra_gbp: z.number(),
  months_current: z.number().nullable().optional(),
  months_with_extra: z.number().nullable().optional(),
  months_saved: z.number().nullable().optional(),
  interest_current_gbp: z.number().nullable().optional(),
  interest_with_extra_gbp: z.number().nullable().optional(),
  interest_saved_gbp: z.number().nullable().optional(),
  payoff_date: z.string().nullable().optional(),
  incomplete: z.boolean(),
  reason: z.string(),
});

export const debtStrategySchema = z.object({
  strategy: z.string(),
  headline: z.string(),
  message: z.string(),
  scope: z.string().optional().default("all"),
  incomplete: z.boolean().optional().default(false),
  incomplete_reason: z.string().optional().default(""),
  focus_debt_id: z.number().nullable().optional(),
  focus_debt_name: z.string().nullable().optional(),
  debts: z.array(z.record(z.string(), z.unknown())),
  payoff_order: z.array(debtAnalysisItemSchema).optional().default([]),
  milestones: z
    .array(
      z.object({
        month_index: z.number(),
        label: z.string(),
        focus_debt_name: z.string().nullable().optional(),
        remaining_total_gbp: z.number(),
        note: z.string().optional().default(""),
      }),
    )
    .optional()
    .default([]),
  estimated_debt_free_date: z.string().nullable().optional(),
  analysis: z.array(debtAnalysisItemSchema).optional().default([]),
  scenarios: z.array(debtScenarioSchema).optional().default([]),
});

export const dualDebtStrategiesSchema = z.object({
  personal: debtStrategySchema,
  business: debtStrategySchema,
});

export const cashflowPlanIssueSchema = z.object({
  severity: z.string(),
  kind: z.string(),
  message: z.string(),
});

export const cashflowPlanMonthSchema = z.object({
  month: z.string(),
  label: z.string(),
  opening_gbp: z.number(),
  income_gbp: z.number(),
  spending_gbp: z.number(),
  debt_payments_gbp: z.number(),
  closing_gbp: z.number(),
  overdraft_limit_gbp: z.number(),
  headroom_gbp: z.number(),
  breaches_overdraft: z.boolean(),
  notes: z.array(z.string()).optional().default([]),
});

export const scopedCashflowPlanSchema = z.object({
  scope: z.string(),
  starting_bank_gbp: z.number(),
  overdraft_limit_gbp: z.number(),
  overdraft_drawn_gbp: z.number(),
  headroom_gbp: z.number(),
  live_breach: z.boolean(),
  incomplete: z.boolean().optional().default(false),
  incomplete_reason: z.string().optional().default(""),
  months: z.array(cashflowPlanMonthSchema).optional().default([]),
  issues: z.array(cashflowPlanIssueSchema).optional().default([]),
  card_warnings: z.array(z.string()).optional().default([]),
});

export const dualCashflowPlansSchema = z.object({
  personal: scopedCashflowPlanSchema,
  business: scopedCashflowPlanSchema,
  personal_overdraft_limit_gbp: z.number(),
  business_overdraft_limit_gbp: z.number(),
});

export const budgetPlanLineSchema = z.object({
  id: z.number().nullable().optional(),
  scope: financeScopeSchema,
  category: z.string(),
  amount_gbp: z.number(),
  source: z.string(),
  source_note: z.string(),
  is_custom: z.boolean(),
  sort_order: z.number(),
  subcategory: z.string().optional().default(""),
  basis_json: z.string().optional().default("{}"),
  confidence: z.string().optional().default(""),
  insufficient_data: z.boolean().optional().default(false),
});

export const budgetTotalsSchema = z.object({
  income_gbp: z.number(),
  committed_gbp: z.number(),
  total_spending_gbp: z.number(),
  debt_payment_gbp: z.number(),
  debt_overpayment_gbp: z.number(),
  buffer_gbp: z.number(),
  discretionary_gbp: z.number(),
  tax_reserve_gbp: z.number(),
  surplus_gbp: z.number(),
  shortfall_gbp: z.number(),
});

export const budgetGapSchema = z.object({
  field: z.string(),
  message: z.string(),
  href: z.string(),
});

export const budgetPlanSchema = z.object({
  id: z.number(),
  name: z.string(),
  style: z.string(),
  origin: z.string(),
  notes: z.string(),
  explanation: z.string(),
  debt_intensity: z.string(),
  cash_buffer_target_gbp: z.number(),
  discretionary_gbp: z.number(),
  tax_reserve_gbp: z.number(),
  income_gbp: z.number(),
  is_active: z.boolean(),
  active_scope: z.string().optional().default(""),
  totals: budgetTotalsSchema,
  lines: z.array(budgetPlanLineSchema),
  created_at: z.string(),
  updated_at: z.string(),
});

export const suggestedBudgetOptionSchema = z.object({
  style: z.string(),
  name: z.string(),
  explanation: z.string(),
  debt_intensity: z.string(),
  cash_buffer_target_gbp: z.number(),
  discretionary_gbp: z.number(),
  tax_reserve_gbp: z.number(),
  income_gbp: z.number(),
  committed_gbp: z.number(),
  debt_payment_gbp: z.number(),
  debt_overpayment_gbp: z.number(),
  surplus_gbp: z.number(),
  shortfall_gbp: z.number(),
  recommended: z.boolean(),
  incomplete: z.boolean(),
  gaps: z.array(budgetGapSchema),
  lines: z.array(budgetPlanLineSchema),
  notes: z.string(),
});

export const budgetSuggestionsSchema = z.object({
  income_gbp: z.number(),
  personal_income_known: z.boolean(),
  default_style: z.string(),
  options: z.array(suggestedBudgetOptionSchema),
  gaps: z.array(budgetGapSchema),
});

export const budgetCompareSchema = z.object({
  income_gbp: z.number(),
  rows: z.array(
    z.object({
      id: z.number().nullable().optional(),
      key: z.string(),
      name: z.string(),
      style: z.string(),
      monthly_total_gbp: z.number(),
      surplus_gbp: z.number(),
      debt_overpayment_gbp: z.number(),
      buffer_gbp: z.number(),
      discretionary_gbp: z.number(),
      tax_reserve_gbp: z.number(),
      shortfall_gbp: z.number(),
      is_active: z.boolean().optional(),
    }),
  ),
});

export const budgetVsActualLineSchema = z.object({
  scope: financeScopeSchema,
  category: z.string(),
  budget_gbp: z.number(),
  actual_gbp: z.number().nullable().optional(),
  variance_gbp: z.number().nullable().optional(),
  percent_used: z.number().nullable().optional(),
  missing_actual: z.boolean().optional().default(false),
  forecast_gbp: z.number().nullable().optional(),
  remaining_gbp: z.number().nullable().optional(),
  actual_source: z.string().optional().default(""),
  transaction_count: z.number().optional().default(0),
});

export const budgetVsActualSchema = z.object({
  month: z.string(),
  plan_id: z.number().nullable().optional(),
  plan_name: z.string().nullable().optional(),
  has_actuals: z.boolean(),
  available: z.boolean().optional().default(true),
  reason: z.string().optional().default(""),
  budgeted_total_gbp: z.number().optional().default(0),
  actual_total_gbp: z.number().optional().default(0),
  variance_total_gbp: z.number().nullable().optional(),
  lines: z.array(budgetVsActualLineSchema),
  unbudgeted_actuals: z.array(budgetVsActualLineSchema).optional().default([]),
});

const quickFileReportLineSchema = z.object({
  nominal_code: z.string().nullable().optional(),
  label: z.string(),
  amount_gbp: z.number(),
});

const quickFileReportSectionSchema = z.object({
  key: z.string(),
  label: z.string(),
  lines: z.array(quickFileReportLineSchema).optional().default([]),
  subtotal_gbp: z.number().nullable().optional(),
  subtotal_label: z.string().nullable().optional(),
  is_total: z.boolean().optional().default(false),
});

export const quickFileProfitAndLossSchema = z.object({
  from_date: z.string(),
  to_date: z.string(),
  turnover_gbp: z.number(),
  cost_of_sales_gbp: z.number(),
  expenses_gbp: z.number(),
  net_profit_gbp: z.number(),
  sections: z.array(quickFileReportSectionSchema).optional().default([]),
});

export const quickFileBalanceSheetSchema = z.object({
  to_date: z.string(),
  fixed_assets_gbp: z.number(),
  current_assets_gbp: z.number(),
  current_liabilities_gbp: z.number(),
  long_term_liabilities_gbp: z.number(),
  capital_and_reserves_gbp: z.number(),
  debtors_gbp: z.number().optional().default(0),
  creditors_gbp: z.number().optional().default(0),
  vat_reserve_gbp: z.number().optional().default(0),
  vat_liability_gbp: z.number().optional().default(0),
  sections: z.array(quickFileReportSectionSchema).optional().default([]),
});

export const quickFileReportsSchema = z.object({
  synced_at: z.string().nullable().optional(),
  profit_and_loss_month: quickFileProfitAndLossSchema.nullable().optional(),
  profit_and_loss_ytd: quickFileProfitAndLossSchema.nullable().optional(),
  balance_sheet: quickFileBalanceSheetSchema.nullable().optional(),
});

const reportCategorySpendSchema = z.object({
  category: z.string(),
  amount_gbp: z.number(),
  transaction_count: z.number().optional().default(0),
});

const reportExpenseLineSchema = z.object({
  id: z.number(),
  posted_on: z.string(),
  description: z.string(),
  category: z.string(),
  amount_gbp: z.number(),
  account_name: z.string().optional().default(""),
});

const reportDebtLineSchema = z.object({
  id: z.number(),
  name: z.string(),
  debt_type: z.string(),
  balance_gbp: z.number(),
  interest_rate_pct: z.number(),
  minimum_payment_gbp: z.number(),
  interest_rate_known: z.boolean().optional().default(true),
});

export const personalFinanceReportSchema = z.object({
  month: z.string(),
  cash_gbp: z.number(),
  overdraft_gbp: z.number().optional().default(0),
  debt_gbp: z.number(),
  pension_gbp: z.number(),
  property_gbp: z.number().optional().default(0),
  net_worth_gbp: z.number(),
  income_gbp: z.number().nullable().optional(),
  spending_gbp: z.number().nullable().optional(),
  surplus_gbp: z.number().nullable().optional(),
  household_bills_gbp: z.number().nullable().optional(),
  debt_repayments_gbp: z.number().nullable().optional(),
  flow_source: z.string().optional().default("none"),
  flow_note: z.string().optional().default(""),
  transaction_count: z.number().optional().default(0),
  spending_by_category: z.array(reportCategorySpendSchema).optional().default([]),
  largest_expenses: z.array(reportExpenseLineSchema).optional().default([]),
  debts: z.array(reportDebtLineSchema).optional().default([]),
  previous_month_income_gbp: z.number().nullable().optional(),
  previous_month_spending_gbp: z.number().nullable().optional(),
  income_change_gbp: z.number().nullable().optional(),
  spending_change_gbp: z.number().nullable().optional(),
  empty_state: z.string().nullable().optional(),
});

export const businessFinanceReportSchema = z.object({
  month: z.string(),
  cash_gbp: z.number(),
  overdraft_gbp: z.number().optional().default(0),
  debt_gbp: z.number(),
  debtors_gbp: z.number().optional().default(0),
  creditors_gbp: z.number().optional().default(0),
  vat_reserve_gbp: z.number().optional().default(0),
  corp_tax_reserve_gbp: z.number().optional().default(0),
  directors_loan_gbp: z.number().optional().default(0),
  company_owes_director_gbp: z.number().optional().default(0),
  director_owes_company_gbp: z.number().optional().default(0),
  company_position_gbp: z.number(),
  turnover_gbp: z.number().nullable().optional(),
  expenses_gbp: z.number().nullable().optional(),
  profit_gbp: z.number().nullable().optional(),
  ytd_turnover_gbp: z.number().nullable().optional(),
  ytd_expenses_gbp: z.number().nullable().optional(),
  ytd_profit_gbp: z.number().nullable().optional(),
  vat_liability_gbp: z.number().nullable().optional(),
  pl_source: z.string().optional().default("none"),
  pl_note: z.string().optional().default(""),
  transaction_count: z.number().optional().default(0),
  spending_by_category: z.array(reportCategorySpendSchema).optional().default([]),
  largest_expenses: z.array(reportExpenseLineSchema).optional().default([]),
  debts: z.array(reportDebtLineSchema).optional().default([]),
  empty_state: z.string().nullable().optional(),
});

export const financeReportsSchema = z.object({
  month: z.string(),
  period: z.string().optional().default("1m"),
  scope: z.string().optional().default("both"),
  personal_period_flow: periodFlowSummarySchema.nullable().optional(),
  business_period_flow: periodFlowSummarySchema.nullable().optional(),
  personal_snapshot: personalFinanceSnapshotSchema.nullable().optional(),
  business_snapshot: businessFinanceSnapshotSchema.nullable().optional(),
  net_worth_gbp: z.number().nullable(),
  total_debt_gbp: z.number().nullable(),
  external_debt_gbp: z.number().nullable().optional(),
  directors_loan_gbp: z.number().optional().default(0),
  debt_reduction_gbp: z.number().nullable().optional(),
  energy_savings_gbp: z.number().optional().default(0),
  energy_savings_vs_forecast: z.string().optional().default(""),
  debt_reduction_available: z.boolean().optional().default(false),
  previous_month_debt_gbp: z.number().nullable().optional(),
  cashflow_history: z
    .array(
      z.object({
        month: z.string(),
        income_gbp: z.number(),
        spending_gbp: z.number(),
        surplus_gbp: z.number(),
      }),
    )
    .optional()
    .default([]),
  debt_history: z
    .array(
      z.object({
        month: z.string(),
        total_debt_gbp: z.number(),
      }),
    )
    .optional()
    .default([]),
  pl_history: z
    .array(
      z.object({
        month: z.string(),
        turnover_gbp: z.number(),
        expenses_gbp: z.number(),
        profit_gbp: z.number(),
      }),
    )
    .optional()
    .default([]),
  quickfile_reports: quickFileReportsSchema.nullable().optional(),
  active_budget: activeBudgetSummarySchema.nullable().optional(),
  budget_vs_actual: budgetVsActualSchema.nullable().optional(),
  personal_report: personalFinanceReportSchema.nullable().optional(),
  business_report: businessFinanceReportSchema.nullable().optional(),
});

export const quickFileConfigStatusSchema = z
  .object({
    account_number: z.string().optional().default(""),
    api_key_set: z.boolean(),
    application_id: z.string().optional().default(""),
    configured: z.boolean(),
    /** True when configured — QuickFile has no separate OAuth token. */
    connected: z.boolean().optional().default(false),
    last_sync_at: z.string().nullable().optional(),
    budget_account_external_ids: z.array(z.string()).optional().default([]),
    last_error: z.string().nullable().optional(),
    quota_exhausted_at: z.string().nullable().optional(),
  })
  .transform((value) => ({
    ...value,
    // Prefer explicit connected; otherwise mirror configured.
    connected: value.connected || value.configured,
  }));

export const quickFileSyncResultSchema = z.object({
  accounts_synced: z.number(),
  debtors_gbp: z.number(),
  reports_synced: z.boolean().optional().default(false),
  imported: z.number().optional().default(0),
  duplicates: z.number().optional().default(0),
  rejected: z.number().optional().default(0),
  message: z.string(),
});

export const financeIntegrationSchema = z.object({
  id: z.string(),
  label: z.string(),
  status: z.string(),
});

export const trueLayerConfigStatusSchema = z.object({
  client_id: z.string(),
  client_secret_set: z.boolean(),
  redirect_uri: z.string(),
  environment: z.string(),
  configured: z.boolean(),
  connected: z.boolean(),
  last_sync_at: z.string().nullable().optional(),
});

export const lunchFlowConfigStatusSchema = z.object({
  api_key_set: z.boolean(),
  configured: z.boolean(),
  connected: z.boolean(),
  last_sync_at: z.string().nullable().optional(),
  provider: z.string().optional(),
});

export const lunchFlowSyncResultSchema = z.object({
  accounts_synced: z.number(),
  message: z.string(),
});

export const trueLayerSyncResultSchema = z.object({
  accounts_synced: z.number(),
  message: z.string(),
  funding_circle_imported: z.boolean().optional(),
  funding_circle_message: z.string().optional(),
});

export const fundingCircleConfigStatusSchema = z.object({
  configured: z.boolean(),
  auto_sync: z.boolean(),
  outstanding_gbp: z.number().nullable().optional(),
  original_gbp: z.number().nullable().optional(),
  apr_pct: z.number(),
  minimum_payment_gbp: z.number(),
  payment_day: z.number().nullable().optional(),
  last_sync_at: z.string().nullable().optional(),
  last_source: z.string(),
  last_txn_on: z.string().optional(),
  message: z.string(),
});

export const fundingCircleSyncResultSchema = z.object({
  imported: z.boolean(),
  balance_gbp: z.number(),
  repayments_applied_gbp: z.number(),
  source: z.string(),
  message: z.string(),
});

export const oidcStatusSchema = z.object({
  enabled: z.boolean(),
});

export type ActiveBudgetSummary = z.infer<typeof activeBudgetSummarySchema>;
export type PeriodFlowSummary = z.infer<typeof periodFlowSummarySchema>;
export type OverviewLineItem = z.infer<typeof overviewLineItemSchema>;
export type OverviewSideBreakdown = z.infer<typeof overviewSideBreakdownSchema>;
export type FinanceDataGaps = z.infer<typeof financeDataGapsSchema>;
export type FinanceOverview = z.infer<typeof financeOverviewSchema>;
export type FinanceAccount = z.infer<typeof financeAccountSchema>;
export type FinanceLiability = z.infer<typeof financeLiabilitySchema>;
export type FinanceInsight = z.infer<typeof financeInsightSchema>;
export type PersonalFinanceSnapshot = z.infer<typeof personalFinanceSnapshotSchema>;
export type BusinessFinanceSnapshot = z.infer<typeof businessFinanceSnapshotSchema>;
export type MonthlyBudgetLine = z.infer<typeof monthlyBudgetLineSchema>;
export type CashflowForecast = z.infer<typeof cashflowForecastSchema>;
export type DebtStrategy = z.infer<typeof debtStrategySchema>;
export type DualDebtStrategies = z.infer<typeof dualDebtStrategiesSchema>;
export type ScopedCashflowPlan = z.infer<typeof scopedCashflowPlanSchema>;
export type DualCashflowPlans = z.infer<typeof dualCashflowPlansSchema>;
export type FinanceReports = z.infer<typeof financeReportsSchema>;
export type PersonalFinanceReport = z.infer<typeof personalFinanceReportSchema>;
export type BusinessFinanceReport = z.infer<typeof businessFinanceReportSchema>;
export type QuickFileProfitAndLossSummary = z.infer<typeof quickFileProfitAndLossSchema>;
export type QuickFileReportSection = z.infer<typeof quickFileReportSectionSchema>;
export type QuickFileReports = z.infer<typeof quickFileReportsSchema>;
export type QuickFileConfigStatus = z.infer<typeof quickFileConfigStatusSchema>;
export type QuickFileSyncResult = z.infer<typeof quickFileSyncResultSchema>;
export type FinanceIntegration = z.infer<typeof financeIntegrationSchema>;
export type LunchFlowConfigStatus = z.infer<typeof lunchFlowConfigStatusSchema>;
export type LunchFlowSyncResult = z.infer<typeof lunchFlowSyncResultSchema>;
export type TrueLayerConfigStatus = z.infer<typeof trueLayerConfigStatusSchema>;
export type TrueLayerSyncResult = z.infer<typeof trueLayerSyncResultSchema>;
export type FundingCircleConfigStatus = z.infer<typeof fundingCircleConfigStatusSchema>;
export type FundingCircleSyncResult = z.infer<typeof fundingCircleSyncResultSchema>;
export type BudgetPlan = z.infer<typeof budgetPlanSchema>;
export type BudgetPlanLine = z.infer<typeof budgetPlanLineSchema>;
export type BudgetTotals = z.infer<typeof budgetTotalsSchema>;
export type SuggestedBudgetOption = z.infer<typeof suggestedBudgetOptionSchema>;
export type BudgetSuggestions = z.infer<typeof budgetSuggestionsSchema>;
export type BudgetCompare = z.infer<typeof budgetCompareSchema>;
export type BudgetVsActual = z.infer<typeof budgetVsActualSchema>;
export type DebtAnalysisItem = z.infer<typeof debtAnalysisItemSchema>;
export type DebtScenario = z.infer<typeof debtScenarioSchema>;

/** Coerce common API null/empty quirks so one bad row cannot blank Position tiles. */
function coerceFinanceRow(raw: unknown): unknown {
  if (!raw || typeof raw !== "object") return raw;
  const row = raw as Record<string, unknown>;
  const dla = row.dla_direction;
  return {
    ...row,
    provider: row.provider ?? "",
    notes: row.notes ?? "",
    overpayment_gbp: row.overpayment_gbp ?? 0,
    dla_direction: dla === "" || dla === undefined ? null : dla,
  };
}

/** Parse account lists without failing the whole page on a single bad row. */
export function parseFinanceAccounts(raw: unknown): FinanceAccount[] {
  if (!Array.isArray(raw)) return [];
  const out: FinanceAccount[] = [];
  for (const item of raw) {
    const parsed = financeAccountSchema.safeParse(coerceFinanceRow(item));
    if (parsed.success) out.push(parsed.data);
  }
  return out;
}

/** Parse liability lists without failing the whole page on a single bad row. */
export function parseFinanceLiabilities(raw: unknown): FinanceLiability[] {
  if (!Array.isArray(raw)) return [];
  const out: FinanceLiability[] = [];
  for (const item of raw) {
    const parsed = financeLiabilitySchema.safeParse(coerceFinanceRow(item));
    if (parsed.success) out.push(parsed.data);
  }
  return out;
}
