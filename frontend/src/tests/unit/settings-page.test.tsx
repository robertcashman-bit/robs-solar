import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import SettingsPage from "@/app/settings/page";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: { username: "admin", role: "admin" },
    loading: false,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/settings",
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    get: vi.fn(async (path: string) => {
      if (path === "/capabilities") {
        return {
          adapter: {
            mode: "simulator",
            supports_read: true,
            supports_write: true,
            supported_writes: ["export_limit"],
            notes: [],
          },
          data_source: "simulated",
          read_only: true,
          enable_live_writes: false,
          sunsynk_enable_unverified_writes: false,
          plant_id: null,
          plant_name: null,
        };
      }
      if (path === "/health") {
        return { status: "ok", adapter_mode: "simulator", read_only: true, timestamp: new Date().toISOString() };
      }
      return {};
    }),
  },
}));

describe("SettingsPage", () => {
  it("shows adapter mode and live writes disabled", async () => {
    const user = userEvent.setup();
    render(<SettingsPage />);
    expect(await screen.findByText("Safety & configuration")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Energy / Solar" }));
    expect(screen.getByText("Remote access")).toBeInTheDocument();
    expect(screen.getAllByText("simulator").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Simulated data")).toBeInTheDocument();
    expect(screen.getByText(/Live writes disabled/i)).toBeInTheDocument();
  });
});
