import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FinanceOverviewView } from "@/components/finance/FinanceOverviewView";
import { financeOverviewSchema, type FinanceOverview } from "@/lib/finance-schemas";

const overview: FinanceOverview = financeOverviewSchema.parse({
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
  available_cash_gbp: 10500,
  available_credit_gbp: 1200,
  credit_limit_gbp: 2000,
  personal_overdraft_gbp: 0,
  business_overdraft_gbp: 0,
  total_assets_gbp: 60500,
  property_gbp: 0,
  month_budgeted_gbp: 2800,
  month_actual_gbp: 400,
  active_budget: {
    id: 1,
    name: "Balanced",
    style: "balanced",
    monthly_total_gbp: 2800,
    surplus_gbp: 400,
    debt_overpayment_gbp: 150,
    buffer_target_gbp: 300,
    income_gbp: 4000,
  },
  insights: [],
});

describe("FinanceOverviewView", () => {
  it("keeps a genuine zero external debt instead of falling back to total debt", () => {
    render(
      <FinanceOverviewView
        overview={{
          ...overview,
          external_debt_gbp: 0,
          total_personal_debt_gbp: 0,
          total_business_debt_gbp: 0,
          directors_loan_gbp: 1200,
          total_debt_gbp: 1200,
        }}
      />,
    );
    const tile = screen.getByText("External debt").closest("div");
    expect(tile).toHaveTextContent("£0.00");
    expect(tile).not.toHaveTextContent("£1,200.00");
  });

  it("renders balance tiles", () => {
    render(<FinanceOverviewView overview={overview} />);
    expect(screen.getByText("Combined net worth")).toBeInTheDocument();
    expect(screen.getByText("Personal net worth")).toBeInTheDocument();
    expect(screen.getByText("Company position")).toBeInTheDocument();
    expect(screen.getByText("Pension")).toBeInTheDocument();
    expect(screen.getByText("Property")).toBeInTheDocument();
    expect(screen.getByText("Director's loan")).toBeInTheDocument();
    expect(screen.getByText("Cash available")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Active Budget" })).toBeInTheDocument();
    expect(screen.getByText(/Balanced · balanced/i)).toBeInTheDocument();
    expect(screen.getByText("Planned expenditure")).toBeInTheDocument();
    expect(
      screen.getByText(/Property value is not set but a mortgage is recorded/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Connect banks" })).toHaveAttribute(
      "href",
      "/finance/connect",
    );
  });

  it("wires dismiss on insights when a handler is provided", async () => {
    const onDismissInsight = vi.fn();
    render(
      <FinanceOverviewView
        overview={{
          ...overview,
          insights: [
            {
              id: 9,
              category: "cashflow",
              severity: "warning",
              title: "Personal cash may be tight after expected bills",
              message: "After household bills, about 200 GBP remains.",
              status: "active",
              created_at: "2026-08-01T00:00:00Z",
            },
          ],
        }}
        onDismissInsight={onDismissInsight}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismissInsight).toHaveBeenCalledWith(9);
  });

  it("hides leftover energy insights", () => {
    render(
      <FinanceOverviewView
        overview={{
          ...overview,
          insights: [
            {
              id: 11,
              category: "energy",
              severity: "info",
              title: "Solar savings this month are below forecast",
              message: "Latest daily saving is below the 7-day average.",
              status: "active",
              created_at: "2026-08-01T00:00:00Z",
            },
          ],
        }}
      />,
    );
    expect(screen.queryByText("Solar savings this month are below forecast")).not.toBeInTheDocument();
    expect(screen.queryByText(/Open energy/i)).not.toBeInTheDocument();
  });

  it("labels budget-plan monthly flow as plan, not live cash", () => {
    render(
      <FinanceOverviewView
        overview={{
          ...overview,
          monthly_flow_source: "budget",
          monthly_income_gbp: 4000,
          monthly_spending_gbp: 2200,
          monthly_surplus_gbp: 1800,
          household_bills_gbp: 0,
          safe_to_spend: {
            personal: {
              safe_to_spend_gbp: 0,
              status: "BUDGET_PLAN_ONLY",
              flow_source: "budget",
              flow_note: "Budget plan estimate — not live income or spending",
            },
            combined: {
              safe_to_spend_gbp: 0,
              status: "BUDGET_PLAN_ONLY",
              flow_source: "budget",
              flow_note: "Budget plan estimate — not live income or spending",
            },
          },
        }}
      />,
    );
    expect(screen.getByText("Planned income")).toBeInTheDocument();
    expect(screen.getByText("Planned spending")).toBeInTheDocument();
    expect(screen.getByText("Planned surplus")).toBeInTheDocument();
    expect(
      screen.getAllByText(/Budget plan estimate — not live income or spending/i).length,
    ).toBeGreaterThan(0);
  });

  it("labels open-banking monthly flow as live sync", () => {
    render(
      <FinanceOverviewView
        overview={{
          ...overview,
          monthly_flow_source: "open_banking",
          monthly_income_gbp: 2800,
          monthly_spending_gbp: 900,
        }}
      />,
    );
    expect(screen.getAllByText("Monthly income").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/From live Open Banking sync/i).length,
    ).toBeGreaterThan(0);
  });
});
