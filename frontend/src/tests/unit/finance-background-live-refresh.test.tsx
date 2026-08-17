import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useFinanceBackgroundLiveRefresh } from "@/lib/use-finance-background-live-refresh";

const post = vi.fn();
const notify = vi.fn();

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: (...args: unknown[]) => post(...args),
  },
}));

vi.mock("@/lib/finance-events", () => ({
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
    post.mockResolvedValue({ ok: true });
    window.sessionStorage.clear();
  });

  it("refreshes live balances once for admins then notifies pages", async () => {
    render(<Probe role="admin" />);
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

  it("does not call live-refresh for viewers", async () => {
    render(<Probe role="viewer" />);
    await waitFor(() => expect(screen.getByText("idle")).toBeInTheDocument());
    expect(post).not.toHaveBeenCalled();
  });
});
