import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FinanceHistoryCharts } from "@/components/finance/FinanceHistoryCharts";
import type { FinanceReports } from "@/lib/finance-schemas";

const emptyReports: FinanceReports = {
  month: "2026-08",
  personal_snapshot: null,
  business_snapshot: null,
  net_worth_gbp: 0,
  total_debt_gbp: 0,
  debt_reduction_gbp: 0,
  debt_reduction_available: false,
  energy_savings_gbp: 0,
  energy_savings_vs_forecast: "",
  cashflow_history: [],
  debt_history: [],
  pl_history: [],
};

describe("FinanceHistoryCharts", () => {
  it("does not invent a trend when history is missing", () => {
    render(<FinanceHistoryCharts reports={emptyReports} />);
    expect(screen.getByText(/No snapshot history yet/)).toBeInTheDocument();
  });

  it("renders a cashflow chart from real snapshot points", () => {
    render(
      <FinanceHistoryCharts
        reports={{
          ...emptyReports,
          cashflow_history: [
            {
              month: "2026-07",
              income_gbp: 4000,
              spending_gbp: 2000,
              surplus_gbp: 1200,
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("Personal cashflow by month")).toBeInTheDocument();
    expect(screen.queryByText("Recorded total debt")).not.toBeInTheDocument();
  });
});
