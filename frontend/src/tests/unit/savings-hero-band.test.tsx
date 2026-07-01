import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SavingsHeroBand } from "@/components/dashboard/SavingsHeroBand";
import type { LiveMetrics } from "@/lib/schemas";

const metrics: LiveMetrics = {
  pv_power_w: 17,
  battery_soc_pct: 98,
  battery_power_w: 13,
  house_load_w: 30,
  house_load_source: "derived",
  house_load_reported_w: 0,
  grid_import_w: 0,
  grid_export_w: 0,
  inverter_mode: "self_use",
  inverter_status: "online",
  daily_pv_kwh: 12.4,
  daily_import_kwh: 31,
  daily_export_kwh: 5.8,
  timestamp: new Date().toISOString(),
  grid_meter_connected: false,
};

describe("SavingsHeroBand", () => {
  it("shows smart meter KPI when Octopus data is available", () => {
    render(
      <SavingsHeroBand
        metrics={metrics}
        summary={null}
        octopusMeter={{
          configured: true,
          average_power_w: 376,
          consumption_kwh: 0.188,
          interval_start: "2026-07-01T19:00:00Z",
          interval_end: "2026-07-01T19:30:00Z",
          is_current_interval: true,
          message: "",
        }}
      />,
    );
    expect(screen.getByText("Smart meter")).toBeInTheDocument();
    expect(screen.getByText(/30-min average · Octopus/i)).toBeInTheDocument();
    expect(screen.getAllByText(/376/i).length).toBeGreaterThanOrEqual(1);
  });

  it("shows amber callout comparing inverter load to smart meter", () => {
    render(
      <SavingsHeroBand
        metrics={metrics}
        summary={null}
        octopusMeter={{
          configured: true,
          average_power_w: 376,
          consumption_kwh: 0.188,
          interval_start: "2026-07-01T19:00:00Z",
          interval_end: "2026-07-01T19:30:00Z",
          is_current_interval: true,
          message: "",
        }}
      />,
    );
    expect(screen.getByText(/not receiving live grid meter data/i)).toBeInTheDocument();
    expect(screen.getByText(/30-min average\) while the inverter shows/i)).toBeInTheDocument();
  });

  it("shows connecting state while Octopus meter loads", () => {
    render(
      <SavingsHeroBand
        metrics={metrics}
        summary={null}
        octopusMeterLoading
      />,
    );
    expect(screen.getByText("Connecting…")).toBeInTheDocument();
  });
});
