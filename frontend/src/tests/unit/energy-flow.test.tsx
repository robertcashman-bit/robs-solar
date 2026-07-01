import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EnergyFlow } from "@/components/dashboard/EnergyFlow";

const metrics = {
  pv_power_w: 4200,
  battery_soc_pct: 68,
  battery_power_w: 600,
  house_load_w: 1800,
  grid_import_w: 0,
  grid_export_w: 500,
  inverter_mode: "self_use",
  inverter_status: "online",
  daily_pv_kwh: 12.4,
  daily_import_kwh: 3.1,
  daily_export_kwh: 5.8,
  timestamp: new Date().toISOString(),
};

describe("EnergyFlow", () => {
  it("renders energy flow diagram with live values", () => {
    render(<EnergyFlow metrics={metrics} />);
    expect(screen.getByLabelText("Energy flow")).toBeInTheDocument();
    expect(screen.getByText("4,200 W")).toBeInTheDocument();
    expect(screen.getByText("68.0%")).toBeInTheDocument();
  });

  it("shows real battery charge/discharge watts when provided", () => {
    render(<EnergyFlow metrics={metrics} />);
    expect(screen.getByText(/600 W Discharging/i)).toBeInTheDocument();
  });

  it("shows inverter throughput on the hub", () => {
    render(<EnergyFlow metrics={metrics} />);
    expect(screen.getByText("2,300 W")).toBeInTheDocument();
  });
});
