import { z } from "zod";

export const financeScopeSchema = z.enum(["personal", "business"]);

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
  net_worth_estimate_gbp: z.number(),
  monthly_surplus_gbp: z.number(),
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
  horizon_days: z.number(),
  starting_balance_gbp: z.number(),
  projected_balance_gbp: z.number(),
  entries: z.array(cashflowForecastEntrySchema),
  cash_pressure_warning: z.boolean(),
  warning_message: z.string(),
});

export const debtStrategySchema = z.object({
  strategy: z.string(),
  headline: z.string(),
  message: z.string(),
  debts: z.array(z.record(z.string(), z.unknown())),
  estimated_debt_free_date: z.string().nullable().optional(),
});

export const financeReportsSchema = z.object({
  month: z.string(),
  personal_snapshot: personalFinanceSnapshotSchema.nullable().optional(),
  business_snapshot: businessFinanceSnapshotSchema.nullable().optional(),
  net_worth_gbp: z.number(),
  total_debt_gbp: z.number(),
  debt_reduction_gbp: z.number(),
  energy_savings_gbp: z.number(),
  energy_savings_vs_forecast: z.string(),
});

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
