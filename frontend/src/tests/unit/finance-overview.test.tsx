import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FinanceOverviewView } from "@/components/finance/FinanceOverviewView";
import { QuickFileStatements } from "@/components/finance/QuickFileStatements";
import type { FinanceAccount, FinanceOverview, QuickFileReports } from "@/lib/finance-schemas";

const overview: FinanceOverview = {
  personal_bank_balance_gbp: 2500,
  business_bank_balance_gbp: 8000,
  total_personal_debt_gbp: 1200,
  total_business_debt_gbp: 0,
  monthly_income_gbp: 4000,
  monthly_spending_gbp: 2200,
  cash_after_bills_gbp: 1800,
  vat_reserve_gbp: 500,
  corp_tax_reserve_gbp: 300,
  vat_reserve_warning: false,
  corp_tax_reserve_warning: false,
  credit_card_balances_gbp: 800,
  loan_balances_gbp: 400,
  mortgage_balance_gbp: 150000,
  pension_value_gbp: 50000,
  directors_loan_gbp: 0,
  liquid_assets_gbp: 10500,
  long_term_assets_gbp: 475000,
  property_value_gbp: 425000,
  debtors_gbp: 8883,
  total_assets_gbp: 485500,
  short_term_debt_gbp: 1200,
  long_term_debt_gbp: 150000,
  total_debt_gbp: 151200,
  home_equity_gbp: 275000,
  personal_short_term_debt_gbp: 1200,
  personal_long_term_debt_gbp: 150000,
  business_short_term_debt_gbp: 0,
  business_long_term_debt_gbp: 0,
  net_worth_estimate_gbp: 334300,
  monthly_surplus_gbp: 1500,
  personal_monthly_income_gbp: 4000,
  business_monthly_turnover_gbp: 12000,
  business_monthly_expenses_gbp: 4500,
  business_monthly_net_profit_gbp: 7500,
  business_ytd_turnover_gbp: 72000,
  business_ytd_net_profit_gbp: 42000,
  business_income_from_quickfile: true,
  historic_fields: ["personal_bank_balance_gbp", "monthly_income_gbp"],
  insights: [],
};

const accounts: FinanceAccount[] = [
  {
    id: 1,
    scope: "personal",
    account_type: "current",
    name: "Main current",
    provider: "Bank",
    balance_gbp: 2500,
    notes: "",
    source: "manual",
    is_active: true,
    is_historic: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const quickfileReports: QuickFileReports = {
  synced_at: "2026-01-15T10:00:00Z",
  profit_and_loss_month: {
    from_date: "2026-01-01",
    to_date: "2026-01-31",
    turnover_gbp: 12000,
    cost_of_sales_gbp: 2000,
    expenses_gbp: 6500,
    net_profit_gbp: 7500,
  },
  profit_and_loss_ytd: {
    from_date: "2026-04-01",
    to_date: "2026-01-31",
    turnover_gbp: 72000,
    cost_of_sales_gbp: 12000,
    expenses_gbp: 38000,
    net_profit_gbp: 42000,
  },
  balance_sheet: {
    to_date: "2026-01-31",
    fixed_assets_gbp: 5000,
    current_assets_gbp: 15000,
    current_liabilities_gbp: 3000,
    long_term_liabilities_gbp: 8000,
    capital_and_reserves_gbp: 9000,
    debtors_gbp: 8883,
    creditors_gbp: 1200,
    vat_liability_gbp: 500,
  },
};

describe("FinanceOverviewView", () => {
  it("links to business page instead of showing QuickFile reports", () => {
    render(<FinanceOverviewView overview={overview} accounts={accounts} />);
    expect(screen.getByText("Open business finance")).toBeInTheDocument();
    expect(screen.getByText("Personal accounts & net worth")).toBeInTheDocument();
    expect(screen.getByText("Main current")).toBeInTheDocument();
  });
});

describe("QuickFileStatements", () => {
  it("renders P&L account then balance sheet in document mode", () => {
    render(<QuickFileStatements reports={quickfileReports} variant="document" />);
    expect(screen.getByText("Profit & Loss Account")).toBeInTheDocument();
    expect(screen.getByText("Balance Sheet")).toBeInTheDocument();
    expect(screen.getByText("Turnover")).toBeInTheDocument();
    expect(screen.getByText("Less: Cost of sales")).toBeInTheDocument();
    expect(screen.getByText("Net profit")).toBeInTheDocument();
    expect(screen.getByText("Fixed assets")).toBeInTheDocument();
  });
});
