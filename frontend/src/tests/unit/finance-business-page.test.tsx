import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import BusinessFinancePage from "@/app/(finance)/finance/business/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
    authResolved: true,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/finance/business",
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(async (path: string) => {
      if (path === "/finance/accounts?scope=business") {
        return [
          {
            id: 1,
            scope: "business",
            account_type: "vat_reserve",
            name: "Vat Account",
            provider: "quickfile",
            balance_gbp: 0.47,
            notes: "",
            source: "quickfile",
            is_active: true,
            created_at: "2010-01-01T00:00:00Z",
            updated_at: "2010-01-01T00:00:00Z",
          },
        ];
      }
      if (path.startsWith("/finance/period-flow")) {
        return {
          period: "1m",
          scope: "business",
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
      if (path === "/finance/snapshots/business") {
        return [
          {
            id: 9,
            snapshot_date: "2010-01-01",
            turnover_gbp: 9999,
            expenses_gbp: 8888,
            // Stale creditor liability wrongly stored as reserve — must not win.
            vat_reserve_gbp: 2956.27,
            corp_tax_reserve_gbp: 666,
            debtors_gbp: 555,
            creditors_gbp: 444,
            profit_estimate_gbp: 1111,
            cash_available_to_draw_gbp: 2222,
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

describe("BusinessFinancePage", () => {
  it("does not treat an older snapshot as this month's figures", async () => {
    render(<BusinessFinancePage />);
    expect(await screen.findByText("Vat Account")).toBeInTheDocument();
    // VAT pot account wins over stale snapshot liability (2956.27).
    expect(tile("VAT reserve (current)").getByText("£0.47")).toBeInTheDocument();
    expect(tile("Turnover (month)").getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("£9,999.00")).not.toBeInTheDocument();
    expect(screen.queryByText("£2,956.27")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Turnover")).toHaveValue("");
  });
});
