import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LiveInverterSettings } from "@/components/scheduler/LiveInverterSettings";

const settings = {
  inverter_sn: "2601315599",
  plant_id: "537603",
  plant_name: "Greenacre",
  plant_permissions: ["smart.rule.view"],
  write_allowed: false,
  write_denied_reason: "Sunsynk account has view-only access.",
  sys_work_mode: "2",
  sys_work_mode_label: "Selling first",
  energy_mode: "1",
  solar_sell: true,
  export_limit_mode: "2",
  discharge_current_a: 205,
  bands: [
    {
      slot: 2,
      start: "06:20",
      end: "11:00",
      target_soc_pct: 19,
      grid_charge_enabled: true,
      power_w: 9000,
    },
  ],
  active_band_slot: 2,
  active_band: {
    slot: 2,
    start: "06:20",
    end: "11:00",
    target_soc_pct: 19,
    grid_charge_enabled: true,
    power_w: 9000,
  },
  diagnosis: "Cap is 19% on the active band · grid charge is ON.",
};

describe("LiveInverterSettings", () => {
  it("renders bands and diagnosis", () => {
    render(<LiveInverterSettings settings={settings} />);
    expect(screen.getByLabelText("Live inverter TOU settings")).toBeInTheDocument();
    expect(screen.getByText(/grid charge is ON/i)).toBeInTheDocument();
    expect(screen.getByText("19%")).toBeInTheDocument();
    expect(screen.getAllByText(/view-only/i).length).toBeGreaterThan(0);
  });
});
