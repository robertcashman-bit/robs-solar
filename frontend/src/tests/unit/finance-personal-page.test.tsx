import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PersonalFinancePage from "@/app/(finance)/finance/personal/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
    authResolved: true,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/finance/personal",
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(async (path: string) => {
      if (path === "/finance/accounts?scope=personal") {
        return [
          {
            id: 1,
            scope: "personal",
            account_type: "current",
            name: "Current",
            provider: "",
            balance_gbp: 13.12,
            notes: "",
            source: "manual",
            is_active: true,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
          {
            id: 2,
            scope: "personal",
            account_type: "pension",
            name: "Pension",
            provider: "",
            balance_gbp: 57726.94,
            notes: "",
            source: "manual",
            is_active: true,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
          {
            id: 3,
            scope: "personal",
            account_type: "property",
            name: "House",
            provider: "",
            balance_gbp: 350000,
            notes: "",
            source: "manual",
            is_active: true,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
        ];
      }
      if (path.startsWith("/finance/liabilities")) {
        return [
          {
            id: 14,
            scope: "personal",
            name: "House mortgage",
            debt_type: "mortgage",
            balance_gbp: 175000,
            interest_rate_pct: 4,
            minimum_payment_gbp: 900,
            overpayment_gbp: 0,
            original_balance_gbp: null,
            payment_day: null,
            credit_limit_gbp: null,
            account_id: null,
            notes: "",
            source: "manual",
            is_active: true,
            interest_rate_known: true,
            dla_direction: null,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
          {
            id: 15,
            scope: "personal",
            name: "Director loan",
            debt_type: "directors_loan",
            balance_gbp: 10287.1,
            interest_rate_pct: 0,
            minimum_payment_gbp: 0,
            overpayment_gbp: 0,
            original_balance_gbp: null,
            payment_day: null,
            credit_limit_gbp: null,
            account_id: null,
            notes: "",
            source: "manual",
            is_active: true,
            interest_rate_known: true,
            dla_direction: "director_owes_company",
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
        ];
      }
      if (path.startsWith("/finance/period-flow")) {
        return {
          period: "1m",
          scope: "personal",
          label: "Last month",
          date_from: "2026-07-01",
          date_to: "2026-07-31",
          months_requested: 1,
          months_with_data: 0,
          transaction_count: 0,
          income_gbp: 0,
          spending_gbp: 0,
          surplus_gbp: 0,
          history_partial: true,
          coverage_note: "No stored transactions in last month.",
        };
      }
      if (path.startsWith("/finance/pnl-compare")) {
        return { scope: "personal", as_of: "2026-08-18", rows: [] };
      }
      if (path.startsWith("/finance/budgets/active")) {
        return null;
      }
      if (path === "/finance/snapshots/personal") {
        return [
          {
            id: 4,
            snapshot_date: "2010-01-01",
            monthly_income_gbp: 9999,
            monthly_spending_gbp: 100,
            household_bills_gbp: 50,
            debt_repayments_gbp: 10,
            surplus_deficit_gbp: 9889,
            notes: "",
            created_at: "2010-01-01T00:00:00Z",
          },
        ];
      }
      return [];
    }),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

function tile(label: string) {
  const heading = screen.getAllByText(label).find((node) => node.tagName === "P");
  const card = heading?.closest("div");
  if (!card) {
    throw new Error(`No tile for ${label}`);
  }
  return within(card);
}

describe("PersonalFinancePage", () => {
  it("does not show an older snapshot as this month's income or surplus", async () => {
    render(<PersonalFinancePage />);
    expect(await screen.findByText("£407,740.06")).toBeInTheDocument();
    expect(tile("Personal monthly income").getByText("—")).toBeInTheDocument();
    expect(tile("Personal monthly surplus").getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("£9,999.00")).not.toBeInTheDocument();
    expect(screen.queryByText("£9,889.00")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Income")).toHaveValue("");
    expect(screen.getByText("Personal house (your half)")).toBeInTheDocument();
    expect(screen.getByText("Your half of £700,000. Other half ignored.")).toBeInTheDocument();
    expect(screen.getByText("Of which house mortgage (placeholder)")).toBeInTheDocument();
    const mortgageRow = screen.getByText("Of which house mortgage (placeholder)").closest("li");
    expect(mortgageRow).toHaveTextContent("£175,000.00");
    expect(screen.getByText(/From the personal mortgage liability/)).toBeInTheDocument();
    expect(tile("Personal assets").getByText("£407,740.06")).toBeInTheDocument();
    expect(tile("Personal debts").getByText("£175,000.00")).toBeInTheDocument();
    expect(screen.getByText("Director's loan payable")).toBeInTheDocument();
    expect(screen.queryByText("Director's loan receivable")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Income, spend & surplus" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "This month to date" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "This month to date" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});
