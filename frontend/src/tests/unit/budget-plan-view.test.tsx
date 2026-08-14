import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BudgetPlanView } from "@/components/finance/BudgetPlanView";
import type { BudgetSuggestions } from "@/lib/finance-schemas";

const emptyTotals = {
  view: "consolidated",
  income_gbp: 0,
  essential_gbp: 0,
  debt_minimum_gbp: 0,
  debt_overpayment_gbp: 0,
  tax_provision_gbp: 0,
  buffer_gbp: 0,
  discretionary_gbp: 0,
  other_gbp: 0,
  committed_gbp: 0,
  allocated_gbp: 0,
  surplus_gbp: null,
  income_complete: false,
  has_missing_inputs: true,
  is_deficit: false,
  incomplete_reason: "Projected surplus unavailable — monthly income needs input.",
};

const suggestions: BudgetSuggestions = {
  recommended_strategy: "stabilise",
  fingerprint: "abc",
  missing: [
    {
      code: "personal_income",
      message: "No personal income snapshot on file. Monthly income needs input.",
      record_href: "/finance/personal",
    },
  ],
  source_notes: [],
  tax: { notes: [] },
  cash: { savings_accounts_found: false },
  suggestions: [
    {
      strategy: "stabilise",
      name: "Stabilise",
      recommended: true,
      items: [
        {
          key: "personal:income:snapshot:1:pay",
          scope: "personal",
          kind: "income",
          category: "Personal income",
          amount_gbp: null,
          source: "snapshot",
          source_label: "From active income record",
          is_generated: true,
          is_user_override: false,
          is_transfer: false,
          is_missing: true,
          notes: "",
        },
      ],
      missing: [],
      source_notes: [],
      tax: { notes: [] },
      cash: { savings_accounts_found: false },
      fingerprint: "abc",
      totals_personal: emptyTotals,
      totals_business: emptyTotals,
      totals_consolidated: emptyTotals,
    },
    {
      strategy: "balanced",
      name: "Balanced",
      recommended: false,
      items: [],
      missing: [],
      source_notes: [],
      tax: { notes: [] },
      cash: { savings_accounts_found: false },
      fingerprint: "abc",
      totals_personal: emptyTotals,
      totals_business: emptyTotals,
      totals_consolidated: emptyTotals,
    },
    {
      strategy: "debt_attack",
      name: "Debt Attack",
      recommended: false,
      items: [],
      missing: [],
      source_notes: [],
      tax: { notes: [] },
      cash: { savings_accounts_found: false },
      fingerprint: "abc",
      totals_personal: emptyTotals,
      totals_business: emptyTotals,
      totals_consolidated: emptyTotals,
    },
    {
      strategy: "custom",
      name: "Custom",
      recommended: false,
      items: [],
      missing: [],
      source_notes: [],
      tax: { notes: [] },
      cash: { savings_accounts_found: false },
      fingerprint: "abc",
      totals_personal: emptyTotals,
      totals_business: emptyTotals,
      totals_consolidated: emptyTotals,
    },
  ],
  saved_plans: [],
  active_plan_id: null,
};

const noop = vi.fn();

describe("BudgetPlanView", () => {
  it("starts with a create-first-budget action when nothing is saved", async () => {
    const user = userEvent.setup();
    render(
      <BudgetPlanView
        suggestions={suggestions}
        canWrite
        saving={false}
        onSave={noop}
        onActivate={noop}
        onDeactivate={noop}
        onDuplicate={noop}
        onReset={noop}
        onRefresh={noop}
        onDelete={noop}
        onLoadPlan={async () => null}
      />,
    );
    expect(screen.getByRole("status", { name: "Create your first budget" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Create your first budget" }));
    expect(screen.getByRole("heading", { name: "Budget options" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Needs attention" })).toBeInTheDocument();
    expect(screen.getByText("Missing / needs input")).toBeInTheDocument();
    expect(screen.getAllByText(/surplus unavailable/i).length).toBeGreaterThan(0);
  });
});
