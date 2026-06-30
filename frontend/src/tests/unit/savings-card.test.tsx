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

  it("shows empty state when no summary", () => {
    render(<SavingsCard summary={null} />);
    expect(screen.getByText(/No summary data yet/i)).toBeInTheDocument();
  });
});
