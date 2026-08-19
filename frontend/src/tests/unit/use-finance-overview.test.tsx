import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FINANCE_LAST_OVERVIEW_KEY } from "@/lib/finance-local-cache";
import { financeOverviewSchema } from "@/lib/finance-schemas";
import { useFinanceOverview } from "@/lib/use-finance-overview";

const get = vi.fn();
const post = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: (...args: unknown[]) => get(...args),
    post: (...args: unknown[]) => post(...args),
  },
}));

vi.mock("@/lib/use-finance-background-live-refresh", () => ({
  useFinanceBackgroundLiveRefresh: () => ({ refreshing: false }),
}));

const stored = financeOverviewSchema.parse({
  personal_bank_balance_gbp: 2500,
  business_bank_balance_gbp: 8000,
  total_personal_debt_gbp: 1200,
  total_business_debt_gbp: 0,
  monthly_income_gbp: 4000,
  monthly_spending_gbp: 2200,
  cash_after_bills_gbp: 1800,
  vat_reserve_gbp: 500,
  corp_tax_reserve_gbp: 300,
  vat_reserve_warning: false,
  corp_tax_reserve_warning: false,
  credit_card_balances_gbp: 800,
  loan_balances_gbp: 400,
  mortgage_balance_gbp: 150000,
  pension_value_gbp: 50000,
  directors_loan_gbp: 0,
  net_worth_estimate_gbp: 100000,
  monthly_surplus_gbp: 1500,
  insights: [],
  generated_at: "2026-08-17T15:32:00+00:00",
  cached: true,
});

function Probe() {
  const { overview, loading, refresh, error } = useFinanceOverview({
    username: "rob",
    role: "admin",
  });
  return (
    <div>
      <p>{loading ? "loading" : "ready"}</p>
      <p>{overview ? `cash:${overview.personal_bank_balance_gbp}` : "none"}</p>
      <p>{error ? `err:${error}` : "no-error"}</p>
      <button type="button" onClick={() => void refresh()}>
        Refresh
      </button>
    </div>
  );
}

describe("useFinanceOverview", () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("paints last saved figures immediately without a loading wait", async () => {
    window.localStorage.setItem(FINANCE_LAST_OVERVIEW_KEY, JSON.stringify(stored));
    get.mockImplementation(
      () =>
        new Promise(() => {
          // never resolve — proves the first paint did not wait on the network
        }),
    );
    render(<Probe />);
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("cash:2500")).toBeInTheDocument();
    await waitFor(() => expect(get).toHaveBeenCalled());
  });

  it("requests overview with personal and business period query params", async () => {
    function PeriodProbe() {
      const { overview } = useFinanceOverview(
        { username: "rob", role: "admin" },
        { personalPeriod: "3m", businessPeriod: "6m" },
      );
      return <p>{overview ? "loaded" : "waiting"}</p>;
    }
    get.mockResolvedValue({
      ...stored,
      personal_period_flow: null,
      business_period_flow: null,
    });
    render(<PeriodProbe />);
    await waitFor(() => expect(get).toHaveBeenCalled());
    const url = String(get.mock.calls[0][0]);
    expect(url).toContain("personal_period=3m");
    expect(url).toContain("business_period=6m");
  });

  it("clears the live-refresh race timer so a fast POST does not reject later", async () => {
    vi.useFakeTimers();
    const rejections: unknown[] = [];
    const onUnhandled = (event: PromiseRejectionEvent) => {
      rejections.push(event.reason);
    };
    window.addEventListener("unhandledrejection", onUnhandled);

    get.mockResolvedValue({
      ...stored,
      personal_bank_balance_gbp: 2600,
      personal_period_flow: null,
      business_period_flow: null,
    });
    post.mockResolvedValue({});

    render(<Probe />);
    await act(async () => {
      await Promise.resolve();
    });
    await act(async () => {
      screen.getByRole("button", { name: "Refresh" }).click();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(8_000);
    });
    window.removeEventListener("unhandledrejection", onUnhandled);
    vi.useRealTimers();

    expect(rejections).toEqual([]);
    expect(post).toHaveBeenCalledWith("/finance/live-refresh", {});
    expect(get.mock.calls.some((call) => String(call[0]).includes("fresh=1"))).toBe(true);
  });
});