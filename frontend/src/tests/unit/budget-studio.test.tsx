import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { BudgetStudio } from "@/components/finance/BudgetStudio";

const balanced = {
  style: "balanced",
  name: "Balanced",
  explanation: "Keep a buffer and pay down expensive debt.",
  debt_intensity: "medium",
  cash_buffer_target_gbp: 300,
  discretionary_gbp: 200,
  tax_reserve_gbp: 0,
  income_gbp: 4252.6,
  committed_gbp: 800,
  debt_payment_gbp: 150,
  debt_overpayment_gbp: 120,
  surplus_gbp: 400,
  shortfall_gbp: 0,
  recommended: true,
  incomplete: false,
  notes: "",
  gaps: [],
  lines: [
    {
      id: null,
      scope: "personal",
      category: "Food",
      amount_gbp: 250,
      source: "suggested",
      source_note: "Suggested",
      is_custom: false,
      sort_order: 10,
    },
  ],
};

const suggestions = {
  income_gbp: 4252.6,
  personal_income_known: true,
  default_style: "balanced",
  options: [
    { ...balanced, style: "stabilise", name: "Stabilise", recommended: false },
    balanced,
    { ...balanced, style: "debt_attack", name: "Debt Attack", recommended: false },
  ],
  gaps: [],
};

const createdPlan = {
  id: 7,
  name: "Balanced",
  style: "balanced",
  origin: "suggested",
  notes: "",
  explanation: balanced.explanation,
  debt_intensity: "medium",
  cash_buffer_target_gbp: 300,
  discretionary_gbp: 200,
  tax_reserve_gbp: 0,
  income_gbp: 4252.6,
  is_active: true,
  totals: {
    income_gbp: 4252.6,
    committed_gbp: 800,
    total_spending_gbp: 1120,
    debt_payment_gbp: 150,
    debt_overpayment_gbp: 120,
    buffer_gbp: 300,
    discretionary_gbp: 200,
    tax_reserve_gbp: 0,
    surplus_gbp: 400,
    shortfall_gbp: 0,
  },
  lines: balanced.lines,
  created_at: "2026-08-15T00:00:00Z",
  updated_at: "2026-08-15T00:00:00Z",
};

const get = vi.fn(async (path: string) => {
  if (path === "/finance/budgets/suggestions") return suggestions;
  if (path === "/finance/budgets") return [];
  if (path === "/finance/budgets/compare") return { income_gbp: 4252.6, rows: [] };
  if (path.startsWith("/finance/budgets/vs-actual")) {
    return {
      month: "2026-08",
      plan_id: null,
      plan_name: null,
      has_actuals: false,
      available: false,
      reason: "No active budget.",
      budgeted_total_gbp: 0,
      actual_total_gbp: 0,
      variance_total_gbp: null,
      lines: [],
      unbudgeted_actuals: [],
    };
  }
  if (path.startsWith("/finance/budget?")) return [];
  return [];
});

const post = vi.fn(async (path: string) => {
  if (path === "/finance/budgets/from-suggestion") return createdPlan;
  if (path === "/finance/budgets/7/activate") return createdPlan;
  return createdPlan;
});

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: (...args: unknown[]) => get(...(args as [string])),
    post: (...args: unknown[]) => post(...(args as [string])),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: string }) => <a href={href}>{children}</a>,
}));

describe("BudgetStudio", () => {
  it("offers the first-time Stabilise / Balanced / Debt Attack flow", async () => {
    const user = userEvent.setup();
    render(<BudgetStudio user={{ username: "admin", role: "admin" }} />);

    expect(await screen.findByRole("heading", { name: "Create your first budget" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save recommended Balanced and set active" }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Budget options" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Stabilise" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Balanced" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Debt Attack" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Save recommended Balanced and set active" }));
    await waitFor(() => {
      expect(post).toHaveBeenCalledWith("/finance/budgets/from-suggestion", {
        style: "balanced",
        name: "Balanced",
        activate: true,
      });
    });
    expect(await screen.findByText("Budget saved and set as active")).toBeInTheDocument();
  });
});
