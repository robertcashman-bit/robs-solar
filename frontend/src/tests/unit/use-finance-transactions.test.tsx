import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FINANCE_LAST_TRANSACTIONS_KEY } from "@/lib/finance-local-cache";
import {
  FINANCE_TXN_PAGE_SIZE,
  useFinanceTransactions,
} from "@/lib/use-finance-transactions";

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
  dateFrom: "",
  dateTo: "",
  scope: "both",
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

function pageRows(startId: number, count: number) {
  return Array.from({ length: count }, (_, i) => ({
    id: startId + i,
    posted_on: `2026-07-${String(27 - (i % 20)).padStart(2, "0")}`,
    description: `Txn ${startId + i}`,
    amount_gbp: -1,
    category: "Food",
    scope: "personal",
    is_transfer: false,
    account_name: "Current",
  }));
}

function LoadMoreProbe() {
  const { rows, hasMore, loadMore, loading } = useFinanceTransactions(
    { username: "rob", role: "admin" },
    "all",
    "",
    "2025-08-21",
    "2026-08-21",
    "both",
  );
  return (
    <div>
      <p>{loading ? "loading" : "ready"}</p>
      <p>count:{rows.length}</p>
      <p>last:{rows[rows.length - 1]?.description ?? "none"}</p>
      {hasMore ? (
        <button type="button" onClick={() => void loadMore()}>
          Load more
        </button>
      ) : null}
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

  it("Load more appends with offset=50 then offset=100", async () => {
    const user = userEvent.setup();
    get.mockImplementation(async (path: string) => {
      if (String(path).startsWith("/finance/categories")) {
        return [{ parent: "Food", scope: "personal" }];
      }
      const url = new URL(String(path), "http://local");
      const offset = Number(url.searchParams.get("offset") || "0");
      if (offset === 0) return pageRows(1, FINANCE_TXN_PAGE_SIZE);
      if (offset === 50) return pageRows(51, FINANCE_TXN_PAGE_SIZE);
      if (offset === 100) return pageRows(101, FINANCE_TXN_PAGE_SIZE);
      return pageRows(151, 10);
    });

    render(<LoadMoreProbe />);
    await waitFor(() => expect(screen.getByText("count:50")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Load more" })).toBeInTheDocument();

    const txnCalls = () =>
      get.mock.calls
        .map((args) => String(args[0]))
        .filter((path) => path.startsWith("/finance/transactions"));

    expect(txnCalls().some((path) => path.includes("offset=0"))).toBe(true);

    await user.click(screen.getByRole("button", { name: "Load more" }));
    await waitFor(() => expect(screen.getByText("count:100")).toBeInTheDocument());
    expect(txnCalls().some((path) => path.includes("offset=50"))).toBe(true);

    await user.click(screen.getByRole("button", { name: "Load more" }));
    await waitFor(() => expect(screen.getByText("count:150")).toBeInTheDocument());
    expect(txnCalls().some((path) => path.includes("offset=100"))).toBe(true);

    // Append must not wipe earlier pages (stale reload would snap back to 50).
    expect(screen.getByText("count:150")).toBeInTheDocument();
  });

  it("treats a full-page cache without hasMore as still pageable", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem(
      FINANCE_LAST_TRANSACTIONS_KEY,
      JSON.stringify({
        filter: "all",
        q: "",
        dateFrom: "2025-08-21",
        dateTo: "2026-08-21",
        scope: "both",
        rows: pageRows(1, FINANCE_TXN_PAGE_SIZE),
        categories: ["Food"],
        // legacy / truncated cache omitted hasMore
      }),
    );
    get.mockImplementation(async (path: string) => {
      if (String(path).startsWith("/finance/categories")) {
        return [{ parent: "Food", scope: "personal" }];
      }
      const url = new URL(String(path), "http://local");
      const offset = Number(url.searchParams.get("offset") || "0");
      if (offset === 0) return pageRows(1, FINANCE_TXN_PAGE_SIZE);
      if (offset === 50) return pageRows(51, 10);
      return [];
    });

    render(<LoadMoreProbe />);
    expect(screen.getByText("count:50")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load more" })).toBeInTheDocument();

    await waitFor(() =>
      expect(
        get.mock.calls.some((args) => String(args[0]).includes("offset=0")),
      ).toBe(true),
    );

    await user.click(screen.getByRole("button", { name: "Load more" }));
    await waitFor(() => expect(screen.getByText("count:60")).toBeInTheDocument());
    const txnPaths = get.mock.calls
      .map((args) => String(args[0]))
      .filter((path) => path.startsWith("/finance/transactions"));
    expect(txnPaths.some((path) => path.includes("offset=50"))).toBe(true);
  });
});
