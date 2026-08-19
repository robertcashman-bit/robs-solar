import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DebtsPage from "@/app/(finance)/finance/debts/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
    authResolved: true,
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

  it("does not flash a false empty-debts state before load finishes", async () => {
    const { apiClient } = await import("@/lib/api-client");
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
      if (path === "/finance/liabilities") {
        await gate;
        return [];
      }
      if (path === "/finance/debts/strategy") {
        await gate;
        return {
          strategy: "none",
          headline: "No active debts",
          message: "Add liabilities on the Debts page.",
          debts: [],
          analysis: [],
          scenarios: [],
        };
      }
      return [];
    });

    render(<DebtsPage />);
    expect(await screen.findByText("Loading debts…")).toBeInTheDocument();
    expect(screen.queryByText("No debts recorded yet")).not.toBeInTheDocument();

    release();
    expect(await screen.findByText("No debts recorded yet")).toBeInTheDocument();
    expect(screen.queryByText("Loading debts…")).not.toBeInTheDocument();
  });
});
