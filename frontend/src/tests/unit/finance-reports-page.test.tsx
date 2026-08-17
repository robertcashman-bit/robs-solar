import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ReportsPage from "@/app/(finance)/finance/reports/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
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
    expect(screen.getByRole("heading", { name: "Active Budget" })).toBeInTheDocument();
    expect(screen.getByText("No budget is active yet.")).toBeInTheDocument();
    expect(screen.getByText("Budget vs actual")).toBeInTheDocument();
    expect(screen.getByText("Live QuickFile statements")).toBeInTheDocument();
    expect(screen.getByText("Company P&L history")).toBeInTheDocument();
    expect(screen.getByText("Account statements")).toBeInTheDocument();
    expect(screen.getByText("Lloyds")).toBeInTheDocument();
  });
});
