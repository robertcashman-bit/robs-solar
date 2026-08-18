import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ReportsPage from "@/app/(finance)/finance/reports/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
    authResolved: true,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/finance/reports",
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(async (path: string) => {
      if (path.startsWith("/finance/reports")) {
        return {
          month: "2026-08",
          personal_snapshot: null,
          business_snapshot: null,
          personal_report: {
            month: "2026-08",
            cash_gbp: 1200,
            overdraft_gbp: 0,
            debt_gbp: 200,
            pension_gbp: 0,
            property_gbp: 0,
            net_worth_gbp: 1000,
            income_gbp: null,
            spending_gbp: null,
            surplus_gbp: null,
            flow_source: "none",
            flow_note: "No personal snapshot or imported transactions for this month.",
            transaction_count: 0,
            spending_by_category: [],
            largest_expenses: [],
            debts: [],
            empty_state:
              "No personal snapshot or imported transactions for this month. Save a snapshot on Personal, or import a statement.",
          },
          net_worth_gbp: 1000,
          total_debt_gbp: 200,
          debt_reduction_gbp: null,
          debt_reduction_available: false,
          pl_history: [
            { month: "2026-07", turnover_gbp: 8000, expenses_gbp: 3000, profit_gbp: 5000 },
          ],
        };
      }
      if (path === "/finance/accounts") {
        return [
          {
            id: 1,
            scope: "personal",
            account_type: "current",
            name: "Lloyds",
            provider: "",
            balance_gbp: 1200,
            notes: "",
            source: "manual",
            is_active: true,
            created_at: "2026-08-01T00:00:00Z",
            updated_at: "2026-08-01T00:00:00Z",
          },
        ];
      }
      if (path.startsWith("/finance/budgets/active")) {
        return null;
      }
      return [];
    }),
  },
}));

describe("ReportsPage", () => {
  it("renders fetched report fields including unavailable debt reduction", async () => {
    render(<ReportsPage />);
    expect(await screen.findByLabelText("Report month")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Net worth")).toBeInTheDocument();
    });
    expect(screen.queryByText("Energy savings")).not.toBeInTheDocument();
    expect(screen.queryByText(/Sunsynk|Octopus|Tesla/i)).not.toBeInTheDocument();
    expect(screen.getByText("Against original balances where recorded")).toBeInTheDocument();
    expect(screen.queryByText("Personal snapshot")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Personal" })).toBeInTheDocument();
    expect(screen.getByText(/Save a snapshot on Personal/i)).toBeInTheDocument();
    expect(screen.getByText("Personal cash")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Active budgets" })).toBeInTheDocument();
    expect(screen.getByText("No active personal plan yet.")).toBeInTheDocument();
    expect(screen.getByText("No active business plan yet.")).toBeInTheDocument();
    expect(screen.getByText("Budget vs actual")).toBeInTheDocument();
    expect(screen.getByText("Live QuickFile statements")).toBeInTheDocument();
    expect(screen.getByText("Company P&L history")).toBeInTheDocument();
    expect(screen.getByText("Account statements")).toBeInTheDocument();
    expect(screen.getByText("Lloyds")).toBeInTheDocument();
  });
});
