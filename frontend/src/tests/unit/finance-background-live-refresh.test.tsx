import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";

const post = vi.fn();
const notify = vi.fn();
const getCsrfToken = vi.fn(() => "csrf-ready" as string | null);
const bootstrapCsrfToken = vi.fn(async () => "csrf-ready" as string | null);

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: (...args: unknown[]) => post(...args),
  },
  getCsrfToken: () => getCsrfToken(),
  bootstrapCsrfToken: () => bootstrapCsrfToken(),
}));

vi.mock("@/lib/finance-events", () => ({
  FINANCE_OVERVIEW_READY_EVENT: "robs-finance-overview-ready",
  notifyFinanceChanged: () => notify(),
}));

function Probe({ role }: { role: "admin" | "viewer" }) {
  const { refreshing } = useFinanceBackgroundLiveRefresh({
    username: "rob",
    role,
  });
  return <p>{refreshing ? "refreshing" : "idle"}</p>;
}

describe("useFinanceBackgroundLiveRefresh", () => {
  beforeEach(() => {
    post.mockReset();
    notify.mockReset();
    getCsrfToken.mockReset();
    bootstrapCsrfToken.mockReset();
    post.mockResolvedValue({ ok: true });
    getCsrfToken.mockReturnValue("csrf-ready");
    bootstrapCsrfToken.mockResolvedValue("csrf-ready");
    window.sessionStorage.clear();
  });

  it("refreshes live balances once for admins then notifies pages", async () => {
    render(<Probe role="admin" />);
    window.dispatchEvent(new Event("robs-finance-overview-ready"));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/finance/live-refresh", {}));
    await waitFor(() => expect(notify).toHaveBeenCalled());
    expect(await screen.findByText("idle")).toBeInTheDocument();
  });

  it("skips refresh inside the session cooldown", async () => {
    window.sessionStorage.setItem("robs-finance-live-refresh-at", String(Date.now()));
    render(<Probe role="admin" />);
    await waitFor(() => expect(screen.getByText("idle")).toBeInTheDocument());
    expect(post).not.toHaveBeenCalled();
  });

  it("does not call live-refresh before the dashboard is ready", async () => {
    render(<Probe role="admin" />);
    await new Promise((resolve) => window.setTimeout(resolve, 80));
    expect(post).not.toHaveBeenCalled();
  });

  it("does not call live-refresh for viewers", async () => {
    render(<Probe role="viewer" />);
    await waitFor(() => expect(screen.getByText("idle")).toBeInTheDocument());
    expect(post).not.toHaveBeenCalled();
  });

  it("bootstraps CSRF before posting live-refresh when memory token is empty", async () => {
    getCsrfToken.mockReturnValueOnce(null).mockReturnValue("boot-csrf");
    bootstrapCsrfToken.mockImplementation(async () => {
      getCsrfToken.mockReturnValue("boot-csrf");
      return "boot-csrf";
    });
    render(<Probe role="admin" />);
    window.dispatchEvent(new Event("robs-finance-overview-ready"));
    await waitFor(() => expect(bootstrapCsrfToken).toHaveBeenCalled());
    await waitFor(() => expect(post).toHaveBeenCalledWith("/finance/live-refresh", {}));
  });
});
