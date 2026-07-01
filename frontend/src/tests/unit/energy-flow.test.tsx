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
    expect(screen.getByLabelText("Live power now")).toBeInTheDocument();
    expect(screen.getByText("4,200 W")).toBeInTheDocument();
    expect(screen.getByText("68.0%")).toBeInTheDocument();
  });

  it("shows real battery charge/discharge watts when provided", () => {
    render(<EnergyFlow metrics={metrics} />);
    expect(screen.getByText(/600 W Discharging/i)).toBeInTheDocument();
  });

  it("shows inverter throughput on the hub", () => {
    render(<EnergyFlow metrics={metrics} />);
    expect(screen.getByText("4,800 W")).toBeInTheDocument();
  });

  it("shows small grid import instead of 0 W Idle", () => {
    render(
      <EnergyFlow
        metrics={{
          ...metrics,
          grid_import_w: 13,
          grid_export_w: 0,
          house_load_w: 250,
          battery_power_w: 150,
          pv_power_w: 75,
        }}
      />,
    );
    expect(screen.getByText("13 W")).toBeInTheDocument();
    expect(screen.getByText("Importing")).toBeInTheDocument();
    expect(screen.queryByText("Idle")).not.toBeInTheDocument();
  });

  it("derives home and inverter load for low-load solar plus grid snapshot", () => {
    render(
      <EnergyFlow
        metrics={{
          ...metrics,
          pv_power_w: 9,
          grid_import_w: 11,
          grid_export_w: 0,
          house_load_w: 0,
          battery_power_w: 0,
          battery_soc_pct: 98,
          grid_meter_connected: true,
        }}
      />,
    );
    expect(screen.getAllByText("20 W").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("11 W")).toBeInTheDocument();
    expect(screen.getByText("Importing")).toBeInTheDocument();
    expect(screen.getByText("Idle")).toBeInTheDocument();
  });

  it("shows Minimal home load when exporting surplus with unreadable load CT", () => {
    render(
      <EnergyFlow
        metrics={{
          ...metrics,
          pv_power_w: 95,
          grid_import_w: 0,
          grid_export_w: 125,
          house_load_w: 0,
          house_load_source: "minimal" as const,
          battery_power_w: 26,
          battery_soc_pct: 98,
        }}
      />,
    );
    expect(screen.getByText("Minimal")).toBeInTheDocument();
    expect(screen.getByText("Surplus to grid")).toBeInTheDocument();
    expect(screen.getByText("Exporting surplus")).toBeInTheDocument();
  });

  it("shows live-now heading and derived-load transparency badge", () => {
    render(
      <EnergyFlow
        metrics={{
          ...metrics,
          pv_power_w: 9,
          grid_import_w: 12,
          grid_export_w: 0,
          house_load_w: 22,
          house_load_source: "derived" as const,
          house_load_reported_w: 0,
          battery_power_w: 1,
          battery_soc_pct: 98,
        }}
      />,
    );
    expect(screen.getByText("Live power (now)")).toBeInTheDocument();
    expect(screen.getByText(/Today's kWh totals are in the cards below/i)).toBeInTheDocument();
    expect(screen.getByText(/Load estimated from balance/i)).toBeInTheDocument();
  });

  it("warns when grid meter unknown with derived load and grid import above floor", () => {
    render(
      <EnergyFlow
        metrics={{
          ...metrics,
          pv_power_w: 17,
          grid_import_w: 12,
          grid_export_w: 0,
          house_load_w: 30,
          house_load_source: "derived" as const,
          house_load_reported_w: 0,
          battery_power_w: 1,
          battery_soc_pct: 98,
          grid_meter_connected: null,
        }}
      />,
    );
    expect(
      screen.getByText(/not receiving live grid meter data|estimated from the inverter only/i),
    ).toBeInTheDocument();
  });

  it("shows Inverter CT only on grid node when meter limited", () => {
    render(
      <EnergyFlow
        metrics={{
          ...metrics,
          pv_power_w: 17,
          grid_import_w: 12,
          grid_export_w: 0,
          house_load_w: 30,
          house_load_source: "derived" as const,
          house_load_reported_w: 0,
          battery_power_w: 1,
          battery_soc_pct: 98,
          grid_meter_connected: false,
        }}
      />,
    );
    expect(screen.getByText(/Inverter CT only/i)).toBeInTheDocument();
  });

  it("shows meter avg on home node when Octopus data available", () => {
    render(
      <EnergyFlow
        metrics={{
          ...metrics,
          pv_power_w: 17,
          grid_import_w: 0,
          grid_export_w: 0,
          house_load_w: 30,
          house_load_source: "derived" as const,
          house_load_reported_w: 0,
          battery_power_w: 13,
          battery_soc_pct: 98,
          grid_meter_connected: false,
        }}
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
    expect(screen.getByText(/Meter avg 376 W/i)).toBeInTheDocument();
  });

  it("warns when Sunsynk grid meter is not connected in cloud feed", () => {
    render(
      <EnergyFlow
        metrics={{
          ...metrics,
          pv_power_w: 17,
          grid_import_w: 0,
          grid_export_w: 0,
          house_load_w: 30,
          house_load_source: "derived" as const,
          house_load_reported_w: 0,
          battery_power_w: 13,
          battery_soc_pct: 98,
          grid_meter_connected: false,
        }}
      />,
    );
    expect(screen.getByText(/not receiving live grid meter data/i)).toBeInTheDocument();
    expect(screen.getByText(/smart meter measures whole-home draw/i)).toBeInTheDocument();
  });

  it("shows Octopus smart meter half-hour average when available", () => {
    render(
      <EnergyFlow
        metrics={{
          ...metrics,
          pv_power_w: 17,
          grid_import_w: 0,
          grid_export_w: 0,
          house_load_w: 30,
          house_load_source: "derived" as const,
          battery_power_w: 13,
          battery_soc_pct: 98,
        }}
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
    expect(screen.getByText(/Smart meter \(Octopus\): 376 W average/i)).toBeInTheDocument();
    expect(screen.getByText(/updates every 30 min/i)).toBeInTheDocument();
  });

  it("shows kW-scale grid and home when a heavy load draws", () => {
    render(
      <EnergyFlow
        metrics={{
          ...metrics,
          pv_power_w: 0,
          grid_import_w: 2800,
          grid_export_w: 0,
          house_load_w: 2700,
          house_load_source: "reported" as const,
          battery_power_w: 100,
          battery_soc_pct: 55,
        }}
      />,
    );
    expect(screen.getByText("2,800 W")).toBeInTheDocument();
    expect(screen.getByText("2,700 W")).toBeInTheDocument();
    expect(screen.getByText("Importing")).toBeInTheDocument();
    expect(screen.queryByText("Load estimated from balance")).not.toBeInTheDocument();
  });
});
