import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnalyticsCharts } from "@/components/analytics/AnalyticsCharts";

const history = {
  range: "day" as const,
  points: [
    {
      timestamp: new Date().toISOString(),
      pv_power_w: 2000,
      battery_soc_pct: 60,
      house_load_w: 1500,
      grid_import_w: 100,
      grid_export_w: 500,
    },
  ],
};

const summary = {
  range: "day" as const,
  pv_kwh: 5,
  consumption_kwh: 4,
  import_kwh: 1,
  export_kwh: 2,
  self_consumption_pct: 60,
  import_cost: 0.28,
  export_credit: 0.3,
  net_cost: -0.02,
  estimated_cost_without_solar: 1.12,
  savings: 1.14,
  currency: "GBP",
};

describe("AnalyticsCharts", () => {
  it("renders range selector and power chart", () => {
    render(
      <AnalyticsCharts
        history={history}
        summary={summary}
        range="day"
        onRangeChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("tab", { name: "Day" })).toBeInTheDocument();
    expect(screen.getByText("Power over time")).toBeInTheDocument();
    expect(screen.getByText("Battery SOC")).toBeInTheDocument();
  });

  it("calls onRangeChange when week selected", async () => {
    const user = userEvent.setup();
    const onRangeChange = vi.fn();
    render(
      <AnalyticsCharts
        history={history}
        summary={summary}
        range="day"
        onRangeChange={onRangeChange}
      />,
    );
    await user.click(screen.getByRole("tab", { name: "Week" }));
    expect(onRangeChange).toHaveBeenCalledWith("week");
  });
});
