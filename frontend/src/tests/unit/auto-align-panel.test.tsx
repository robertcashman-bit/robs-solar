import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AutoAlignPanel } from "@/components/scheduler/AutoAlignPanel";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
  }),
}));

vi.mock("@/lib/api-client", () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
  apiClient: {
    get: vi.fn(async (path: string) => {
      if (path === "/metrics/ev/status") {
        return { car_charging_likely: false, in_dispatch_window: false };
      }
      if (path === "/metrics/peak-import-guard") {
        return {
          enabled: true,
          armed: false,
          last_action_message: "",
          last_audit_ids: [],
          consecutive_samples: 0,
          cooldown_remaining_seconds: 0,
        };
      }
      return {
        enabled: false,
        soc_floor_pct: 20,
        last_run_message: "",
        next_cheap_windows: [],
        computed_bands: [],
      };
    }),
    post: vi.fn(async () => ({
      enabled: true,
      soc_floor_pct: 20,
      last_run_message: "Auto-align disabled",
      next_cheap_windows: [],
      computed_bands: [],
    })),
  },
}));

describe("AutoAlignPanel", () => {
  it("renders enable control for admin", async () => {
    render(<AutoAlignPanel />);
    expect(await screen.findByRole("button", { name: /Enable auto-align/i })).toBeInTheDocument();
  });

  it("calls API when enabling", async () => {
    const user = userEvent.setup();
    const { apiClient } = await import("@/lib/api-client");
    render(<AutoAlignPanel />);
    await screen.findByRole("button", { name: /Enable auto-align/i });
    await user.click(screen.getByRole("button", { name: /Enable auto-align/i }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalled());
  });
});
