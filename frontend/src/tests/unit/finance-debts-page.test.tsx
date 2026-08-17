import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DebtsPage from "@/app/(finance)/finance/debts/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/finance/debts",
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(async (path: string) => {
      if (path === "/finance/liabilities") return [];
      if (path === "/finance/accounts") return [];
      if (path === "/finance/debts/strategy") {
        return {
          strategy: "none",
          headline: "No active debts",
          message: "Add liabilities on the Debts page.",
          debts: [],
        };
      }
      return [];
    }),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe("DebtsPage", () => {
  it("includes a minimum payment field on the add-debt form", async () => {
    render(<DebtsPage />);
    expect(await screen.findByPlaceholderText("Minimum payment")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Overpayment")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add debt" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Credit limit")).toBeInTheDocument();
  });
});
