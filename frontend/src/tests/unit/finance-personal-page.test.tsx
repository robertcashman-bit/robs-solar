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
            balance_gbp: 120,
            notes: "",
            source: "manual",
            is_active: true,
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
    expect(await screen.findByText("Current")).toBeInTheDocument();
    expect(tile("Monthly income").getByText("—")).toBeInTheDocument();
    expect(tile("Monthly surplus").getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("£9,999.00")).not.toBeInTheDocument();
    expect(screen.queryByText("£9,889.00")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Income")).toHaveValue("");
  });
});
