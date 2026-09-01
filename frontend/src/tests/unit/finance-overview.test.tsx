import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  FinanceOverviewView,
  fallbackBusinessBreakdown,
  fallbackPersonalBreakdown,
} from "@/components/finance/FinanceOverviewView";
import { financeOverviewSchema, type FinanceOverview } from "@/lib/finance-schemas";

vi.mock("@/components/finance/ActiveBudgetsBreakdown", () => ({
  ActiveBudgetsBreakdown: () => null,
}));

const overview: FinanceOverview = financeOverviewSchema.parse({
  personal_bank_balance_gbp: 2500,
  business_bank_balance_gbp: -6290,
  total_personal_debt_gbp: 87410.5,
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
  personal_loan_balances_gbp: 4000,
  mortgage_balance_gbp: 82210.5,
  pension_value_gbp: 50000,
  directors_loan_gbp: 9037,
  net_worth_estimate_gbp: 223800,
  monthly_surplus_gbp: 1500,
  personal_overdraft_gbp: 200,
  business_overdraft_gbp: 6290,
  property_gbp: 350000,
  debtors_gbp: 1200,
  personal_net_worth_gbp: 226300,
  company_position_gbp: -2500,
  company_owes_director_gbp: 9037,
  mortgage_configured: true,
  pension_configured: true,
  insights: [],
  personal_breakdown: {
    side: "personal",
    owned_total_gbp: 402500,
    owed_total_gbp: 87210.5,
    whats_left_gbp: 226300,
    whats_left_available: true,
    whats_left_hint: "",
    owned: [
      { key: "personal_bank", label: "Bank", amount_gbp: 2500, kind: "asset", tier: "primary", hint: "" },
      { key: "house_share", label: "House share", amount_gbp: 350000, kind: "asset", tier: "primary", hint: "Your half only" },
      { key: "pension", label: "Pension", amount_gbp: 50000, kind: "asset", tier: "primary", hint: "" },
    ],
    owed: [
      {
        key: "mortgage",
        label: "House mortgage",
        amount_gbp: 82210.5,
        kind: "debt",
        tier: "primary",
        hint: "Your half of the £164,421 joint mortgage",
      },
      { key: "personal_cards", label: "Credit cards", amount_gbp: 800, kind: "debt", tier: "primary", hint: "" },
      { key: "personal_loans", label: "Loans", amount_gbp: 4000, kind: "debt", tier: "primary", hint: "" },
      { key: "personal_od", label: "Overdraft", amount_gbp: 200, kind: "debt", tier: "primary", hint: "" },
    ],
  },
  business_breakdown: {
    side: "business",
    owned_total_gbp: 22500,
    owed_total_gbp: 25000,
    whats_left_gbp: -2500,
    whats_left_available: true,
    whats_left_hint: "From the Defence Legal balance sheet",
    owned: [
      { key: "business_bank", label: "Bank", amount_gbp: 0, kind: "asset", tier: "primary", hint: "" },
      { key: "customers_owe", label: "Customers still to pay", amount_gbp: 1200, kind: "asset", tier: "primary", hint: "" },
      {
        key: "fixed_assets",
        label: "Vehicles and kit",
        amount_gbp: 18000,
        kind: "asset",
        tier: "primary",
        hint: "From the Defence Legal balance sheet",
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
        tier: "primary",
        hint: "",
      },
      {
        key: "company_owes_robert_biz",
        label: "Company still owes Robert",
        amount_gbp: 9037,
        kind: "debt",
        tier: "primary",
        hint: "",
      },
    ],
  },
});

describe("FinanceOverviewView", () => {
  it("shows personal debts and Tesla HP on first paint without More", () => {
    render(<FinanceOverviewView overview={overview} />);
    const you = screen.getByRole("region", { name: "You" });
    const dls = screen.getByRole("region", { name: "Defence Legal" });
    expect(you).toHaveTextContent("House mortgage");
    expect(you).toHaveTextContent("£82,210.50");
    expect(you).toHaveTextContent("Credit cards");
    expect(you).toHaveTextContent("Loans");
    expect(you).toHaveTextContent("Overdraft");
    expect(dls).toHaveTextContent("Tesla still to pay");
    expect(dls).toHaveTextContent("Vehicles and kit");
    expect(dls).toHaveTextContent("Company still owes Robert");
    expect(dls).toHaveTextContent("From the Defence Legal balance sheet");
    expect(dls).toHaveTextContent("-£2,500.00");
    expect(screen.queryByText("VAT pot")).not.toBeInTheDocument();
  });

  it("keeps VAT pot behind More only", async () => {
    const user = userEvent.setup();
    render(<FinanceOverviewView overview={overview} />);
    expect(screen.queryByText("VAT pot")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "More" }));
    expect(screen.getByText("VAT pot")).toBeInTheDocument();
  });

  it("fallback personal owed lists mortgage cards loans and overdraft", () => {
    const bare = financeOverviewSchema.parse({
      personal_bank_balance_gbp: -200,
      business_bank_balance_gbp: 0,
      total_personal_debt_gbp: 87410.5,
      total_business_debt_gbp: 0,
      monthly_income_gbp: 0,
      monthly_spending_gbp: 0,
      cash_after_bills_gbp: 0,
      vat_reserve_gbp: 0,
      corp_tax_reserve_gbp: 0,
      vat_reserve_warning: false,
      corp_tax_reserve_warning: false,
      credit_card_balances_gbp: 800,
      personal_credit_card_balances_gbp: 800,
      business_credit_card_balances_gbp: 0,
      loan_balances_gbp: 0,
      personal_loan_balances_gbp: 4000,
      mortgage_balance_gbp: 82210.5,
      pension_value_gbp: 0,
      directors_loan_gbp: 0,
      net_worth_estimate_gbp: 0,
      monthly_surplus_gbp: 0,
      personal_overdraft_gbp: 200,
      business_overdraft_gbp: 0,
      property_gbp: 350000,
      personal_net_worth_gbp: 0,
      company_position_gbp: 0,
      mortgage_configured: true,
      pension_configured: false,
      insights: [],
    });
    const fallback = fallbackPersonalBreakdown(bare);
    const labels = fallback.owed.map((line) => line.label);
    expect(labels).toEqual(
      expect.arrayContaining(["House mortgage", "Credit cards", "Loans", "Overdraft"]),
    );
    expect(fallback.owed.every((line) => line.tier === "primary")).toBe(true);
    expect(fallback.owed.some((line) => line.label === "House mortgage" && line.amount_gbp === 82210.5)).toBe(
      true,
    );
    expect(fallback.owed_total_gbp).toBeGreaterThan(0);
    expect(fallback.owed.length).toBeGreaterThan(0);
  });

  it("fallback business owed is never empty when totals say there is debt", () => {
    const bare = financeOverviewSchema.parse({
      personal_bank_balance_gbp: 0,
      business_bank_balance_gbp: -6290,
      total_personal_debt_gbp: 0,
      total_business_debt_gbp: 18000,
      monthly_income_gbp: 0,
      monthly_spending_gbp: 0,
      cash_after_bills_gbp: 0,
      vat_reserve_gbp: 0,
      corp_tax_reserve_gbp: 0,
      vat_reserve_warning: false,
      corp_tax_reserve_warning: false,
      credit_card_balances_gbp: 0,
      loan_balances_gbp: 13000,
      mortgage_balance_gbp: 0,
      pension_value_gbp: 0,
      directors_loan_gbp: 9037,
      net_worth_estimate_gbp: 0,
      monthly_surplus_gbp: 0,
      business_overdraft_gbp: 6290,
      company_owes_director_gbp: 9037,
      company_position_gbp: -35057.5,
      insights: [],
    });
    const fallback = fallbackBusinessBreakdown(bare);
    expect(fallback.owed.length).toBeGreaterThan(0);
    expect(fallback.owed_total_gbp).toBeGreaterThan(0);
    expect(fallback.whats_left_available).toBe(false);
    expect(fallback.whats_left_gbp).toBeNull();
    expect(fallback.whats_left_hint).toMatch(/Balance sheet not synced/i);
    // Must not surface the old working-capital −£35k as What's left.
    expect(fallback.whats_left_gbp).not.toBe(-35057.5);
  });
});
