import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ActiveBudgetsBreakdown } from "@/components/finance/ActiveBudgetsBreakdown";
import type { BudgetPlan } from "@/lib/finance-schemas";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: string }) => <a href={href}>{children}</a>,
}));

const personalPlan: BudgetPlan = {
  id: 1,
  name: "Personal history",
  style: "custom",
  origin: "history",
  notes: "",
  explanation: "From stored personal transactions",
  debt_intensity: "medium",
  cash_buffer_target_gbp: 100,
  discretionary_gbp: 50,
  tax_reserve_gbp: 0,
  income_gbp: 4000,
  is_active: true,
  active_scope: "personal",
  totals: {
    income_gbp: 4000,
    committed_gbp: 900,
    total_spending_gbp: 1100,
    debt_payment_gbp: 100,
    debt_overpayment_gbp: 50,
    buffer_gbp: 100,
    discretionary_gbp: 50,
    tax_reserve_gbp: 0,
    surplus_gbp: 2900,
    shortfall_gbp: 0,
  },
  lines: [
    {
      id: 11,
      scope: "personal",
      category: "Food",
      amount_gbp: 250,
      source: "history",
      source_note: "History",
      is_custom: false,
      sort_order: 10,
      subcategory: "",
      basis_json: "{}",
      confidence: "",
      insufficient_data: false,
    },
    {
      id: 12,
      scope: "personal",
      category: "Utilities",
      amount_gbp: 180,
      source: "history",
      source_note: "History",
      is_custom: false,
      sort_order: 20,
      subcategory: "",
      basis_json: "{}",
      confidence: "",
      insufficient_data: false,
    },
  ],
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

const businessPlan: BudgetPlan = {
  id: 2,
  name: "Business history",
  style: "custom",
  origin: "history",
  notes: "",
  explanation: "From stored business transactions",
  debt_intensity: "medium",
  cash_buffer_target_gbp: 200,
  discretionary_gbp: 0,
  tax_reserve_gbp: 300,
  income_gbp: 8000,
  is_active: true,
  active_scope: "business",
  totals: {
    income_gbp: 8000,
    committed_gbp: 1200,
    total_spending_gbp: 1500,
    debt_payment_gbp: 0,
    debt_overpayment_gbp: 0,
    buffer_gbp: 200,
    discretionary_gbp: 0,
    tax_reserve_gbp: 300,
    surplus_gbp: 6500,
    shortfall_gbp: 0,
  },
  lines: [
    {
      id: 21,
      scope: "business",
      category: "Software / IT",
      amount_gbp: 120,
      source: "history",
      source_note: "History",
      is_custom: false,
      sort_order: 10,
      subcategory: "",
      basis_json: "{}",
      confidence: "",
      insufficient_data: false,
    },
    {
      id: 22,
      scope: "business",
      category: "VAT reserve",
      amount_gbp: 300,
      source: "history",
      source_note: "History",
      is_custom: false,
      sort_order: 20,
      subcategory: "",
      basis_json: "{}",
      confidence: "",
      insufficient_data: false,
    },
  ],
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

const get = vi.fn(async (path: string) => {
  if (path === "/finance/budgets/active?scope=personal") return personalPlan;
  if (path === "/finance/budgets/active?scope=business") return businessPlan;
  return null;
});

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: (...args: unknown[]) => get(...(args as [string])),
  },
}));

describe("ActiveBudgetsBreakdown", () => {
  it("renders personal and business sections with every fixture line", async () => {
    render(
      <ActiveBudgetsBreakdown
        personalPlan={personalPlan}
        businessPlan={businessPlan}
        fetchPlans={false}
        showOpenLink={false}
      />,
    );

    expect(screen.getByRole("heading", { name: "Active budgets" })).toBeInTheDocument();
    expect(screen.getByLabelText("Personal active budget")).toBeInTheDocument();
    expect(screen.getByLabelText("DLS Ltd active budget")).toBeInTheDocument();

    expect(screen.getByText("Food")).toBeInTheDocument();
    expect(screen.getByText("Utilities")).toBeInTheDocument();
    expect(screen.getByText("Software / IT")).toBeInTheDocument();
    expect(screen.getByText("VAT reserve")).toBeInTheDocument();
    expect(screen.getByText("£250.00")).toBeInTheDocument();
    expect(screen.getByText("£180.00")).toBeInTheDocument();
    expect(screen.getByText("£120.00")).toBeInTheDocument();
    expect(screen.getByText("£300.00")).toBeInTheDocument();
    expect(screen.getByText("Personal income")).toBeInTheDocument();
    expect(screen.getByText("Business income")).toBeInTheDocument();
  });

  it("fetches both scoped active plans when not supplied", async () => {
    get.mockClear();
    render(<ActiveBudgetsBreakdown />);
    await waitFor(() => {
      expect(get).toHaveBeenCalledWith("/finance/budgets/active?scope=personal");
      expect(get).toHaveBeenCalledWith("/finance/budgets/active?scope=business");
    });
    expect(await screen.findByText("Food")).toBeInTheDocument();
    expect(screen.getByText("Software / IT")).toBeInTheDocument();
  });

  it("splits a single combined plan into personal and business line lists", async () => {
    const combined: BudgetPlan = {
      ...personalPlan,
      id: 9,
      name: "Combined Balanced",
      active_scope: "",
      income_gbp: 4250,
      lines: [...personalPlan.lines, ...businessPlan.lines],
    };
    render(
      <ActiveBudgetsBreakdown
        personalPlan={combined}
        businessPlan={combined}
        fetchPlans={false}
        showOpenLink={false}
      />,
    );
    expect(screen.getByText("Food")).toBeInTheDocument();
    expect(screen.getByText("Software / IT")).toBeInTheDocument();
    expect(screen.getByText("Personal income")).toBeInTheDocument();
    expect(screen.getByText("Business income")).toBeInTheDocument();
  });
});
