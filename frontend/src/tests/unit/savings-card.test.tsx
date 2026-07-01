import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SavingsCard } from "@/components/dashboard/SavingsCard";

const summary = {
  range: "day" as const,
  pv_kwh: 10.5,
  consumption_kwh: 8.2,
  import_kwh: 1.5,
  export_kwh: 3.8,
  self_consumption_pct: 63.8,
  import_cost: 0.42,
  export_credit: 0.57,
  net_cost: -0.15,
  estimated_cost_without_solar: 2.3,
  savings: 2.45,
  currency: "GBP",
};

describe("SavingsCard", () => {
  it("renders savings and net cost", () => {
    render(<SavingsCard summary={summary} />);
    expect(screen.getByText("Savings & cost")).toBeInTheDocument();
    expect(screen.getByText("£2.45")).toBeInTheDocument();
    expect(screen.getByText("63.8%")).toBeInTheDocument();
  });

  it("prefers live daily totals when provided", () => {
    render(
      <SavingsCard
        summary={summary}
        live={{
          pv_power_w: 100,
          battery_soc_pct: 90,
          house_load_w: 200,
          grid_import_w: 0,
          grid_export_w: 0,
          inverter_mode: "self_use",
          inverter_status: "online",
          daily_pv_kwh: 20,
          daily_import_kwh: 15,
          daily_export_kwh: 2,
          timestamp: new Date().toISOString(),
        }}
      />,
    );
    expect(screen.getByText("15.0 kWh imported")).toBeInTheDocument();
    expect(screen.getByText("90.0%")).toBeInTheDocument();
  });

  it("shows empty state when no summary", () => {
    render(<SavingsCard summary={null} />);
    expect(screen.getByText(/No summary data yet/i)).toBeInTheDocument();
  });
});
