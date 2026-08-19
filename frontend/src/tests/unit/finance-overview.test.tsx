import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FinanceOverviewView } from "@/components/finance/FinanceOverviewView";
import { financeOverviewSchema, type FinanceOverview } from "@/lib/finance-schemas";

vi.mock("@/components/finance/ActiveBudgetsBreakdown", () => ({
  ActiveBudgetsBreakdown: () => (
    <div aria-label="Active budgets by scope">
      <h2>Active budgets</h2>
      <section aria-label="Personal active budget">
        <h3>Personal budget</h3>
        <span>Food</span>
        <span>£250.00</span>
      </section>
      <section aria-label="DLS Ltd active budget">
        <h3>DLS Ltd budget</h3>
        <span>Software / IT</span>
        <span>£120.00</span>
      </section>
    </div>
  ),
}));

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
  mortgage_balance_gbp: 82210.5,
  pension_value_gbp: 50000,
  directors_loan_gbp: 0,
  net_worth_estimate_gbp: 100000,
  monthly_surplus_gbp: 1500,
  available_cash_gbp: 10500,
  available_credit_gbp: 1200,
  credit_limit_gbp: 2000,
  personal_overdraft_gbp: 0,
  business_overdraft_gbp: 0,
  total_assets_gbp: 405500,
  property_gbp: 350000,
  debtors_gbp: 1200,
  personal_net_worth_gbp: 226300,
  company_position_gbp: 9700,
  month_budgeted_gbp: 2800,
  month_actual_gbp: 400,
  mortgage_configured: true,
  pension_configured: true,
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
    const tile = screen.getByText("Combined external debt").closest("div");
    expect(tile).toHaveTextContent("£0.00");
    // Headline stays £0; DLA may appear only in the excludes-hint.
    expect(tile?.querySelector(".text-2xl")).toHaveTextContent("£0.00");
    expect(tile).toHaveTextContent(/Excludes director's loan £1,200\.00/);
  });

  it("renders labelled personal, business, and combined stacks with house hints", () => {
    render(<FinanceOverviewView overview={overview} />);
    expect(screen.getByRole("heading", { name: "Net worth" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "This period flow" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Position" })).toBeInTheDocument();
    expect(
      screen.getByText("Combined (personal + company, director's loan counted once)"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Personal net worth").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Business / company position").length).toBeGreaterThan(0);
    expect(screen.getByText("Personal house (your half)")).toBeInTheDocument();
    expect(screen.getByText("Your half of £700,000. Other half ignored.")).toBeInTheDocument();
    expect(screen.getByText("Of which house mortgage")).toBeInTheDocument();
    expect(screen.getByText("Confirmed half-share of £164,421 joint mortgage.")).toBeInTheDocument();
    expect(screen.getByText("Of which personal credit cards")).toBeInTheDocument();
    expect(screen.getByText("High-interest debt")).toBeInTheDocument();
    expect(
      screen.getByText("APR 15% or more across all debts — pay this first"),
    ).toBeInTheDocument();
    expect(screen.getByText("Of which business loans")).toBeInTheDocument();
    expect(
      screen.getByText(/Excludes director's loan/),
    ).toBeInTheDocument();
    expect(screen.getByText("Business VAT pot")).toBeInTheDocument();
    expect(screen.getByText("Business debtors")).toBeInTheDocument();
    expect(screen.queryByText("External debt")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Active budgets" })).toBeInTheDocument();
    expect(screen.getByText("Food")).toBeInTheDocument();
    expect(screen.getByText("Software / IT")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Safe to spend" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Connect banks" })).toHaveAttribute(
      "href",
      "/finance/connect",
    );
  });

  it("shows combined cash available as the sum of personal and company net banks", () => {
    render(
      <FinanceOverviewView
        overview={{
          ...overview,
          personal_bank_balance_gbp: -2503.91,
          business_bank_balance_gbp: -1948.6,
          cash_available_gbp: -4452.51,
          available_cash_gbp: 13.23,
          personal_overdraft_gbp: 2517.14,
          business_overdraft_gbp: 1948.6,
        }}
      />,
    );
    const tile = screen.getByText("Combined cash available").closest("div");
    expect(tile).toHaveTextContent("-£4,452.51");
    expect(tile).toHaveTextContent(/-£2,503\.91 personal/);
    expect(tile).toHaveTextContent(/-£1,948\.60 company/);
    expect(tile).not.toHaveTextContent("£13.23");
  });

  it("scope toggle shows only that stack's tiles", async () => {
    const user = userEvent.setup();
    render(<FinanceOverviewView overview={overview} />);
    await user.click(screen.getByRole("button", { name: "personal" }));
    expect(screen.getByText("Personal house (your half)")).toBeInTheDocument();
    expect(screen.queryByText("Business VAT pot")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Combined (personal + company, director's loan counted once)"),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "business" }));
    expect(screen.getByText("Business VAT pot")).toBeInTheDocument();
    expect(screen.queryByText("Personal house (your half)")).not.toBeInTheDocument();
    expect(screen.queryByText("Of which house mortgage")).not.toBeInTheDocument();
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
    expect(screen.getByText("Personal planned income")).toBeInTheDocument();
    expect(screen.getByText("Personal planned spending")).toBeInTheDocument();
    expect(screen.getByText("Personal planned surplus")).toBeInTheDocument();
    expect(
      screen.getAllByText(/Budget plan estimate — not live income or spending/i).length,
    ).toBeGreaterThan(0);
  });

  it("uses historical period flow tiles when ledger totals are present", () => {
    render(
      <FinanceOverviewView
        overview={{
          ...overview,
          personal_period_flow: {
            period: "1m",
            scope: "personal",
            label: "Last month",
            date_from: "2026-07-01",
            date_to: "2026-07-31",
            months_requested: 1,
            months_with_data: 1,
            transaction_count: 4,
            income_gbp: 3100,
            spending_gbp: 900,
            surplus_gbp: 2200,
            history_partial: false,
            coverage_note: "",
          },
          business_period_flow: {
            period: "3m",
            scope: "business",
            label: "3 months",
            date_from: "2026-05-01",
            date_to: "2026-07-31",
            months_requested: 3,
            months_with_data: 2,
            transaction_count: 2,
            income_gbp: 8000,
            spending_gbp: 2500,
            surplus_gbp: 5500,
            history_partial: true,
            coverage_note: "Showing available history from 2026-06-01 (2 of 3 months).",
          },
        }}
      />,
    );
    expect(screen.getByText("Personal income (Last month)")).toBeInTheDocument();
    expect(screen.getByText("Business turnover (3 months)")).toBeInTheDocument();
    expect(screen.getAllByText(/Showing available history from 2026-06-01/).length).toBeGreaterThan(0);
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
    expect(screen.getAllByText("Personal monthly income").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/From live Open Banking sync/i).length,
    ).toBeGreaterThan(0);
  });

  it("shows partial monthly interest when some APRs are still missing", () => {
    render(
      <FinanceOverviewView
        overview={{
          ...overview,
          monthly_interest_gbp: 187.42,
          monthly_interest_incomplete: true,
        }}
      />,
    );
    const tile = screen.getByText("Combined est. monthly interest").closest("div");
    expect(tile).toHaveTextContent("£187.42");
    expect(tile).toHaveTextContent(/some debts still need APR/);
    expect(tile).not.toHaveTextContent("APR required for interest forecast");
  });

  it("explains missing available credit when no limits are recorded", () => {
    render(
      <FinanceOverviewView
        overview={{
          ...overview,
          available_credit_gbp: 0,
          credit_limit_gbp: 0,
        }}
      />,
    );
    const tile = screen.getByText("Available credit").closest("div");
    expect(tile?.querySelector(".text-2xl")).toHaveTextContent("—");
    expect(tile).toHaveTextContent(/No credit limits recorded/);
  });
});
