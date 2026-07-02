import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FinanceOverviewView } from "@/components/finance/FinanceOverviewView";
import type { FinanceOverview } from "@/lib/finance-schemas";

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
  net_worth_estimate_gbp: 100000,
  monthly_surplus_gbp: 1500,
  insights: [],
};

describe("FinanceOverviewView", () => {
  it("renders balance tiles", () => {
    render(<FinanceOverviewView overview={overview} />);
    expect(screen.getByText("Personal bank")).toBeInTheDocument();
    expect(screen.getByText("Business bank")).toBeInTheDocument();
    expect(screen.getByText("Net worth (estimate)")).toBeInTheDocument();
  });
});
