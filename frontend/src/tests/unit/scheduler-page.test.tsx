import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SchedulerPage from "@/app/(energy)/energy/scheduler/page";

const authState = {
  user: { username: "admin", role: "admin" } as { username: string; role: string } | null,
  loading: false,
  logout: vi.fn(),
};

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => authState,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/energy/scheduler",
}));

const { apiPost, settingsResponse } = vi.hoisted(() => ({
  apiPost: vi.fn(async () => ({})),
  settingsResponse: {
    write_allowed: true as boolean,
    inverter_sn: "2601315599",
    plant_id: "537603",
    plant_name: "Greenacre",
    plant_permissions: ["inverter.setting.edit"],
    write_denied_reason: "",
    sys_work_mode: "2",
    sys_work_mode_label: "Selling first",
    energy_mode: "1",
    solar_sell: true,
    export_limit_mode: "2",
    discharge_current_a: 205,
    bands: [
      {
        slot: 1,
        start: "00:00",
        end: "06:00",
        target_soc_pct: 100,
        grid_charge_enabled: true,
        power_w: 3000,
      },
      {
        slot: 2,
        start: "06:00",
        end: "11:00",
        target_soc_pct: 40,
        grid_charge_enabled: false,
        power_w: 8000,
      },
    ],
    active_band_slot: 1,
    active_band: null,
    diagnosis: "",
  },
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
      if (path === "/octopus/prices") return { rates: [] };
      if (path === "/octopus/dispatches") {
        return {
          off_peak_window: { start: "23:30", end: "05:30" },
          planned: [],
          completed: [],
          tariff_family: "IOG",
        };
      }
      if (path === "/controls/settings") return settingsResponse;
      return {};
    }),
    post: apiPost,
  },
}));

describe("SchedulerPage display-only", () => {
  beforeEach(() => {
    authState.user = { username: "admin", role: "admin" };
    settingsResponse.write_allowed = true;
    apiPost.mockClear();
  });

  it("shows live settings and strategy previews without write controls", async () => {
    render(<SchedulerPage />);
    expect(await screen.findByRole("heading", { name: "Time-of-use schedule" })).toBeInTheDocument();
    expect(screen.getByText(/Display only/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Strategy previews" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Edit schedule" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Unlock inverter control" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Confirm & apply/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Auto-align battery to IOG windows" }),
    ).not.toBeInTheDocument();
  });

  it("lets viewers preview strategies without posting schedule writes", async () => {
    authState.user = { username: "viewer", role: "viewer" };
    const user = userEvent.setup();
    render(<SchedulerPage />);
    expect(await screen.findByRole("heading", { name: "Strategy previews" })).toBeInTheDocument();
    const presetButtons = screen.getAllByRole("button").filter((button) =>
      /Preview/i.test(button.textContent ?? ""),
    );
    expect(presetButtons.length).toBeGreaterThan(0);
    await user.click(presetButtons[0]);
    expect(apiPost).not.toHaveBeenCalled();
  });
});
