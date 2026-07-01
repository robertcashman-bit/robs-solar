import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DashboardView } from "@/components/dashboard/DashboardView";

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

describe("DashboardView", () => {
  it("renders loading skeletons", () => {
    render(
      <DashboardView
        metrics={null}
        connectivity={null}
        summary={null}
        compare={null}
        loading
        error={null}
        readOnly
      />,
    );
    expect(screen.getByLabelText("Live dashboard loading")).toBeInTheDocument();
  });

  it("renders live metrics", () => {
    render(
      <DashboardView
        metrics={metrics}
        connectivity={{
          backend_healthy: true,
          adapter_mode: "sunsynk_connect",
          adapter_connected: true,
        }}
        summary={null}
        compare={null}
        loading={false}
        error={null}
        readOnly
      />,
    );
    expect(screen.getByLabelText("Savings control centre KPIs")).toBeInTheDocument();
    expect(screen.getByLabelText("Savings insights")).toBeInTheDocument();
    expect(screen.getAllByText("4,200 W").length).toBeGreaterThan(0);
    expect(screen.getAllByText("68.0%").length).toBeGreaterThan(0);
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("12.4 kWh")).toBeInTheDocument();
    expect(screen.getByText("Read-only")).toBeInTheDocument();
  });

  it("labels live adapter mode on the dashboard", () => {
    render(
      <DashboardView
        metrics={metrics}
        connectivity={{
          backend_healthy: true,
          adapter_mode: "sunsynk_connect",
          adapter_connected: true,
        }}
        summary={null}
        compare={null}
        loading={false}
        error={null}
        readOnly
      />,
    );
    expect(screen.getByText("Live data")).toBeInTheDocument();
  });

  it("shows connecting when adapter mode is not yet known", () => {
    render(
      <DashboardView
        metrics={metrics}
        connectivity={null}
        summary={null}
        compare={null}
        loading={false}
        error={null}
        readOnly
      />,
    );
    expect(screen.getByText("Connecting…")).toBeInTheDocument();
  });

  it("shows IOG import and export rate pills when octopus tariff is provided", () => {
    render(
      <DashboardView
        metrics={metrics}
        connectivity={{
          backend_healthy: true,
          adapter_mode: "sunsynk_connect",
          adapter_connected: true,
        }}
        summary={null}
        compare={null}
        loading={false}
        error={null}
        readOnly
        octopusTariff={{
          import_tariff_code: "E-1R-IOG-KDP-FIX-12M-25-06-20-J",
          import_product_code: "IOG-KDP-FIX-12M-25-06-20",
          import_display_name: "IOG",
          import_rate_pence: 22.38,
          export_tariff_code: "E-1R-OUTGOING-VAR-24-10-26-J",
          export_product_code: "OUTGOING-VAR-24-10-26",
          export_display_name: "OUTGOING",
          export_rate_pence: 12.0,
          standing_charge_pence: null,
          is_variable: false,
          tariff_family: "IOG",
          region: "J",
        }}
        agilePricePence={18.6}
      />,
    );
    expect(screen.getByText("IOG: 22.4p/kWh")).toBeInTheDocument();
    expect(screen.getByText("Export: 12.0p/kWh")).toBeInTheDocument();
    // The generic Agile pill should not appear when account tariff is known.
    expect(screen.queryByText(/Agile now:/)).not.toBeInTheDocument();
  });

  it("falls back to the Agile pill when no account tariff is known", () => {
    render(
      <DashboardView
        metrics={metrics}
        connectivity={{
          backend_healthy: true,
          adapter_mode: "sunsynk_connect",
          adapter_connected: true,
        }}
        summary={null}
        compare={null}
        loading={false}
        error={null}
        readOnly
        octopusTariff={null}
        agilePricePence={18.6}
      />,
    );
    expect(screen.getByText("Agile now: 18.6p/kWh")).toBeInTheDocument();
  });

  it("renders error state", () => {
    render(
      <DashboardView
        metrics={null}
        connectivity={null}
        summary={null}
        compare={null}
        loading={false}
        error="Backend unavailable"
        readOnly
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Backend unavailable");
  });
});
