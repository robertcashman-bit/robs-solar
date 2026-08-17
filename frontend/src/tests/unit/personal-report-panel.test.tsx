import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PersonalReportPanel } from "@/components/finance/PersonalReportPanel";
import type { PersonalFinanceReport } from "@/lib/finance-schemas";

const baseReport: PersonalFinanceReport = {
  month: "2026-08",
  cash_gbp: 1200,
  overdraft_gbp: 0,
  debt_gbp: 4500,
  pension_gbp: 18000,
  property_gbp: 0,
  net_worth_gbp: 14700,
  income_gbp: 3200,
  spending_gbp: 2100,
  surplus_gbp: 1100,
  household_bills_gbp: 800,
  debt_repayments_gbp: 200,
  flow_source: "snapshot",
  flow_note: "From the latest personal snapshot",
  transaction_count: 0,
  spending_by_category: [
    { category: "Groceries", amount_gbp: 420, transaction_count: 8 },
    { category: "Fuel", amount_gbp: 160, transaction_count: 3 },
  ],
  largest_expenses: [
    {
      id: 11,
      posted_on: "2026-08-04",
      description: "Tesco",
      category: "Groceries",
      amount_gbp: 86.4,
      account_name: "Lloyds",
    },
  ],
  debts: [
    {
      id: 2,
      name: "Car loan",
      debt_type: "loan",
      balance_gbp: 4500,
      interest_rate_pct: 6.5,
      minimum_payment_gbp: 200,
      interest_rate_known: true,
    },
  ],
  previous_month_income_gbp: 3000,
  previous_month_spending_gbp: 2300,
  income_change_gbp: 200,
  spending_change_gbp: -200,
  empty_state: null,
};

describe("PersonalReportPanel", () => {
  it("always shows the Personal heading when report is missing", () => {
    render(<PersonalReportPanel report={null} />);
    expect(screen.getByRole("heading", { name: "Personal" })).toBeInTheDocument();
    expect(screen.getByText(/Personal report is unavailable/i)).toBeInTheDocument();
  });

  it("renders headline figures, MoM change, categories, expenses and debts", () => {
    render(<PersonalReportPanel report={baseReport} />);
    expect(screen.getByRole("heading", { name: "Personal" })).toBeInTheDocument();
    expect(screen.getAllByText("From the latest personal snapshot").length).toBeGreaterThan(0);
    expect(screen.getByText("Income")).toBeInTheDocument();
    expect(screen.getByText("Spending")).toBeInTheDocument();
    expect(screen.getByText("Surplus")).toBeInTheDocument();
    expect(screen.getByText("Personal cash")).toBeInTheDocument();
    expect(screen.getByText("Personal debt")).toBeInTheDocument();
    expect(screen.getByText("Pension")).toBeInTheDocument();
    expect(screen.getByText("Personal net worth")).toBeInTheDocument();
    expect(screen.getByText("+£200.00 vs previous month")).toBeInTheDocument();
    expect(screen.getByText("-£200.00 vs previous month")).toBeInTheDocument();
    expect(screen.getByText("Spending by category")).toBeInTheDocument();
    expect(screen.getByText("Groceries")).toBeInTheDocument();
    expect(screen.getByText("Largest expenses")).toBeInTheDocument();
    expect(screen.getByText("Tesco")).toBeInTheDocument();
    expect(screen.getByText("Personal debts")).toBeInTheDocument();
    expect(screen.getByText("Car loan")).toBeInTheDocument();
  });

  it("shows budget flow as planned figures, not unlabeled actuals", () => {
    render(
      <PersonalReportPanel
        report={{
          ...baseReport,
          flow_source: "budget",
          flow_note: "Budget plan estimate — not live income or spending",
          income_change_gbp: null,
          spending_change_gbp: null,
          previous_month_income_gbp: null,
          previous_month_spending_gbp: null,
          spending_by_category: [],
          largest_expenses: [],
        }}
      />,
    );
    expect(screen.getByText("Planned income")).toBeInTheDocument();
    expect(screen.getByText("Planned spending")).toBeInTheDocument();
    expect(screen.getByText("Planned surplus")).toBeInTheDocument();
    expect(
      screen.getAllByText("Budget plan estimate — not live income or spending").length,
    ).toBeGreaterThan(0);
  });

  it("shows empty_state guidance without inventing income figures", () => {
    render(
      <PersonalReportPanel
        report={{
          ...baseReport,
          income_gbp: null,
          spending_gbp: null,
          surplus_gbp: null,
          household_bills_gbp: null,
          debt_repayments_gbp: null,
          flow_source: "none",
          flow_note: "No live sync, snapshot, or budget plan for this month",
          spending_by_category: [],
          largest_expenses: [],
          debts: [],
          income_change_gbp: null,
          spending_change_gbp: null,
          previous_month_income_gbp: null,
          previous_month_spending_gbp: null,
          empty_state:
            "No personal snapshot or imported transactions for this month. Save a snapshot on Personal, or import a statement.",
        }}
      />,
    );
    expect(screen.getByRole("heading", { name: "Personal" })).toBeInTheDocument();
    expect(screen.getByText(/Save a snapshot on Personal/i)).toBeInTheDocument();
    expect(screen.queryByText("Income")).not.toBeInTheDocument();
    expect(screen.queryByText("Spending by category")).not.toBeInTheDocument();
    expect(screen.getByText("Personal cash")).toBeInTheDocument();
  });
});
