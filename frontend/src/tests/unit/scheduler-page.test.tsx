import { render, screen, waitFor } from "@testing-library/react";
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

const settingsResponse = {
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
    { slot: 1, start: "00:00", end: "06:00", target_soc_pct: 100, grid_charge_enabled: true, power_w: 3000 },
    { slot: 2, start: "06:00", end: "11:00", target_soc_pct: 40, grid_charge_enabled: false, power_w: 8000 },
  ],
  active_band_slot: 1,
  active_band: null,
  diagnosis: "",
};

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
      if (path === "/controls/auto-schedule") {
        return {
          enabled: false,
          soc_floor_pct: 20,
          last_run_message: "",
          next_cheap_windows: [],
          computed_bands: [],
        };
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
      if (path === "/metrics/ev/status") {
        return { car_charging_likely: false, in_dispatch_window: false };
      }
      if (path === "/controls/settings") return settingsResponse;
      return {};
    }),
    post: vi.fn(async () => ({})),
  },
}));

describe("SchedulerPage gating", () => {
  beforeEach(() => {
    authState.user = { username: "admin", role: "admin" };
    settingsResponse.write_allowed = true;
  });

  it("shows the editable schedule for an admin when writes are allowed", async () => {
    render(<SchedulerPage />);
    expect(await screen.findByRole("heading", { name: "Edit schedule" })).toBeInTheDocument();
    expect(
      await screen.findByRole("region", { name: "Auto-align battery to IOG windows" }),
    ).toBeInTheDocument();
  });

  it("hides the editor and shows installer access when write is denied", async () => {
    settingsResponse.write_allowed = false;
    render(<SchedulerPage />);
    await waitFor(() =>
      expect(screen.queryByRole("heading", { name: "Edit schedule" })).not.toBeInTheDocument(),
    );
    expect(
      await screen.findByRole("heading", { name: "Unlock inverter control" }),
    ).toBeInTheDocument();
  });

  it("hides the editor for a non-admin viewer", async () => {
    authState.user = { username: "viewer", role: "viewer" };
    render(<SchedulerPage />);
    await screen.findByRole("heading", { name: "Time-of-use scheduler" });
    expect(screen.queryByRole("heading", { name: "Edit schedule" })).not.toBeInTheDocument();
  });
});
