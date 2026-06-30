import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TodayCompareStrip } from "@/components/dashboard/TodayCompareStrip";
import type { MetricCompare } from "@/lib/schemas";

const compare: MetricCompare = {
  range: "day",
  today: {
    range: "day",
    pv_kwh: 1,
    consumption_kwh: 10,
    import_kwh: 5,
    export_kwh: 0,
    self_consumption_pct: 90,
    import_cost: 1.5,
    export_credit: 0,
    net_cost: 1.5,
    estimated_cost_without_solar: 2.8,
    savings: -1.37,
    currency: "GBP",
  },
  yesterday: {
    range: "day",
    pv_kwh: 2,
    consumption_kwh: 8,
    import_kwh: 3,
    export_kwh: 0,
    self_consumption_pct: 95,
    import_cost: 1,
    export_credit: 0,
    net_cost: 1,
    estimated_cost_without_solar: 2.2,
    savings: -2.71,
    currency: "GBP",
  },
  deltas: [
    {
      label: "Savings",
      today: -1.37,
      yesterday: -2.71,
      unit: "GBP",
      higher_is_better: true,
    },
  ],
};

describe("TodayCompareStrip", () => {
  it("shows signed savings headline instead of raw negative currency", () => {
    render(
      <TodayCompareStrip
        compare={compare}
        range="day"
        onRangeChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/more than no-solar/i)).toBeInTheDocument();
    expect(screen.queryByText("£-1.37")).not.toBeInTheDocument();
  });

  it("calls onRangeChange when toggling period", async () => {
    const onRangeChange = vi.fn();
    const user = userEvent.setup();
    render(
      <TodayCompareStrip
        compare={compare}
        range="day"
        onRangeChange={onRangeChange}
      />,
    );
    await user.click(screen.getByRole("button", { name: "week" }));
    expect(onRangeChange).toHaveBeenCalledWith("week");
  });
});
