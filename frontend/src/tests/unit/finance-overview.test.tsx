import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FinanceOverviewView } from "@/components/finance/FinanceOverviewView";
import { financeOverviewSchema, type FinanceOverview } from "@/lib/finance-schemas";

vi.mock("@/components/finance/ActiveBudgetsBreakdown", () => ({
  ActiveBudgetsBreakdown: () => null,
}));

const overview: FinanceOverview = financeOverviewSchema.parse({
  personal_bank_balance_gbp: 2500,
  business_bank_balance_gbp: -6290,
  total_personal_debt_gbp: 83010.5,
  total_business_debt_gbp: 30823,
  monthly_income_gbp: 4000,
  monthly_spending_gbp: 2200,
  cash_after_bills_gbp: 1800,
  vat_reserve_gbp: 500,
  corp_tax_reserve_gbp: 300,
  vat_reserve_warning: false,
  corp_tax_reserve_warning: false,
  credit_card_balances_gbp: 800,
  personal_credit_card_balances_gbp: 800,
  business_credit_card_balances_gbp: 0,
  loan_balances_gbp: 13000,
  personal_loan_balances_gbp: 0,
  mortgage_balance_gbp: 82210.5,
  pension_value_gbp: 50000,
  directors_loan_gbp: 9037,
  net_worth_estimate_gbp: 100000,
  monthly_surplus_gbp: 1500,
  available_cash_gbp: 13,
  available_credit_gbp: 1200,
  credit_limit_gbp: 2000,
  personal_overdraft_gbp: 0,
  business_overdraft_gbp: 6290,
  total_assets_gbp: 405500,
  property_gbp: 350000,
  debtors_gbp: 1200,
  personal_net_worth_gbp: 226300,
  company_position_gbp: -35057.5,
  company_owes_director_gbp: 9037,
  month_budgeted_gbp: 2800,
  month_actual_gbp: 400,
  mortgage_configured: true,
  pension_configured: true,
  insights: [],
  personal_breakdown: {
    side: "personal",
    owned_total_gbp: 402500,
    owed_total_gbp: 83010.5,
    whats_left_gbp: 226300,
    owned: [
      { key: "personal_bank", label: "Bank", amount_gbp: 2500, kind: "asset", tier: "primary", hint: "" },
      { key: "house_share", label: "House share", amount_gbp: 350000, kind: "asset", tier: "primary", hint: "Your half only" },
      { key: "pension", label: "Pension", amount_gbp: 50000, kind: "asset", tier: "primary", hint: "" },
      {
        key: "company_owes_robert",
        label: "Company still owes Robert",
        amount_gbp: 9037,
        kind: "asset",
        tier: "more",
        hint: "",
      },
    ],
    owed: [
      {
        key: "mortgage",
        label: "House mortgage",
        amount_gbp: 82210.5,
        kind: "debt",
        tier: "primary",
        hint: "Your half of the joint mortgage",
      },
      { key: "personal_cards", label: "Credit cards", amount_gbp: 800, kind: "debt", tier: "primary", hint: "" },
    ],
  },
  business_breakdown: {
    side: "business",
    owned_total_gbp: 2000,
    owed_total_gbp: 37150,
    whats_left_gbp: -35057.5,
    owned: [
      { key: "business_bank", label: "Bank", amount_gbp: 0, kind: "asset", tier: "primary", hint: "" },
      {
        key: "customers_owe",
        label: "Customers still to pay",
        amount_gbp: 1200,
        kind: "asset",
        tier: "primary",
        hint: "",
      },
      {
        key: "car_gap",
        label: "Car value not on this list",
        amount_gbp: null,
        kind: "gap",
        tier: "primary",
        hint: "Finance is listed under what you owe, but the car itself is not counted here",
      },
      { key: "vat_pot", label: "VAT pot", amount_gbp: 500, kind: "asset", tier: "more", hint: "" },
    ],
    owed: [
      { key: "business_od", label: "Overdraft", amount_gbp: 6290, kind: "debt", tier: "primary", hint: "" },
      {
        key: "vehicle_hp_1",
        label: "Tesla still to pay",
        amount_gbp: 13000,
        kind: "debt",
        tier: "more",
        hint: "",
      },
      {
        key: "company_owes_robert_biz",
        label: "Company still owes Robert",
        amount_gbp: 9037,
        kind: "debt",
        tier: "more",
        hint: "",
      },
    ],
  },
  personal_period_flow: {
    period: "1m",
    scope: "personal",
    label: "Last month",
    date_from: "2026-08-01",
    date_to: "2026-08-31",
    months_requested: 1,
    months_with_data: 1,
    transaction_count: 4,
    income_gbp: 3100,
    spending_gbp: 900,
    surplus_gbp: 2200,
    history_partial: false,
    coverage_note: "",
    source: "transactions",
    money_in_label: "Money in",
    money_out_label: "Money out",
  },
  business_period_flow: {
    period: "1m",
    scope: "business",
    label: "Last month",
    date_from: "2026-08-01",
    date_to: "2026-08-31",
    months_requested: 1,
    months_with_data: 1,
    transaction_count: 1,
    income_gbp: 18000,
    spending_gbp: 12000,
    surplus_gbp: 6000,
    history_partial: false,
    coverage_note: "",
    source: "quickfile_pnl",
    money_in_label: "Invoiced",
    money_out_label: "Costs",
  },
});

describe("FinanceOverviewView", () => {
  it("shows one hero what's left and two plain-English columns", () => {
    render(<FinanceOverviewView overview={overview} />);
    expect(screen.getByRole("region", { name: "What's left" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "You" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Defence Legal" })).toBeInTheDocument();
    expect(screen.getAllByText("What you own").length).toBe(2);
    expect(screen.getAllByText("What you owe").length).toBe(2);
    expect(screen.getByText("House share")).toBeInTheDocument();
    expect(screen.getByText("Pension")).toBeInTheDocument();
    expect(screen.getByText("Car value not on this list")).toBeInTheDocument();
    expect(screen.queryByText(/net worth/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/company position/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/turnover/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/P&L|P&amp;L/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/external debt/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/director'?s loan/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Show calculation")).not.toBeInTheDocument();
    expect(screen.queryByText("Safe to spend")).not.toBeInTheDocument();
    expect(screen.queryByText("Debt stacks")).not.toBeInTheDocument();
  });

  it("keeps Tesla HP and DLA behind More until expanded", async () => {
    const user = userEvent.setup();
    render(<FinanceOverviewView overview={overview} />);
    expect(screen.queryByText("Tesla still to pay")).not.toBeInTheDocument();
    expect(screen.queryByText("Company still owes Robert")).not.toBeInTheDocument();
    expect(screen.queryByText("VAT pot")).not.toBeInTheDocument();
    const moreButtons = screen.getAllByRole("button", { name: "More" });
    await user.click(moreButtons[1]);
    expect(screen.getByText("Tesla still to pay")).toBeInTheDocument();
    expect(screen.getByText("Company still owes Robert")).toBeInTheDocument();
    expect(screen.getByText("VAT pot")).toBeInTheDocument();
  });

  it("labels Defence Legal money-in as Invoiced, not turnover", () => {
    render(<FinanceOverviewView overview={overview} />);
    expect(screen.getByText("Invoiced")).toBeInTheDocument();
    expect(screen.getByText("Money in")).toBeInTheDocument();
    expect(screen.queryByText(/Business turnover/i)).not.toBeInTheDocument();
  });

  it("says Just 1 September for thin MTD business periods", () => {
    render(
      <FinanceOverviewView
        overview={{
          ...overview,
          business_period_flow: {
            ...overview.business_period_flow!,
            period: "mtd",
            label: "Just 1 September",
            date_from: "2026-09-01",
            date_to: "2026-09-01",
            coverage_note: "Just 1 September. Not a full month of work.",
            income_gbp: 0,
            spending_gbp: 0,
            transaction_count: 0,
          },
        }}
      />,
    );
    expect(screen.getAllByText(/Just 1 September/).length).toBeGreaterThan(0);
  });

  it("does not repeat the combined hero amount inside the columns", () => {
    render(<FinanceOverviewView overview={overview} />);
    const hero = screen.getByRole("region", { name: "What's left" });
    expect(hero).toHaveTextContent("£100,000.00");
    // Column what's-left figures are side-specific, not the combined hero.
    const you = screen.getByRole("region", { name: "You" });
    const dls = screen.getByRole("region", { name: "Defence Legal" });
    expect(you).toHaveTextContent("£226,300.00");
    expect(dls).toHaveTextContent("-£35,057.50");
    expect(you).not.toHaveTextContent("£100,000.00");
    expect(dls).not.toHaveTextContent("£100,000.00");
  });
});
