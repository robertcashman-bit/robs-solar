import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FINANCE_LAST_TRANSACTIONS_KEY } from "@/lib/finance-local-cache";
import { useFinanceTransactions } from "@/lib/use-finance-transactions";

const get = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: (...args: unknown[]) => get(...args),
    post: vi.fn(),
  },
}));

vi.mock("@/lib/use-finance-background-live-refresh", () => ({
  useFinanceBackgroundLiveRefresh: () => ({ refreshing: false }),
}));

const stored = {
  filter: "all",
  q: "",
  rows: [
    {
      id: 7,
      posted_on: "2026-08-01",
      description: "Tesco",
      amount_gbp: -12.4,
      category: "Food",
      scope: "personal",
      is_transfer: false,
      account_name: "Current",
    },
  ],
  categories: ["Food"],
  hasMore: false,
};

function Probe() {
  const { rows, loading } = useFinanceTransactions(
    { username: "rob", role: "admin" },
    "all",
    "",
  );
  return (
    <div>
      <p>{loading ? "loading" : "ready"}</p>
      <p>{rows[0] ? `txn:${rows[0].description}` : "none"}</p>
    </div>
  );
}

describe("useFinanceTransactions", () => {
  beforeEach(() => {
    get.mockReset();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("paints last saved transactions immediately without a loading wait", async () => {
    window.localStorage.setItem(FINANCE_LAST_TRANSACTIONS_KEY, JSON.stringify(stored));
    get.mockImplementation(
      () =>
        new Promise(() => {
          // never resolve — proves first paint did not wait on the network
        }),
    );
    render(<Probe />);
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("txn:Tesco")).toBeInTheDocument();
    await waitFor(() => expect(get).toHaveBeenCalled());
  });
});
