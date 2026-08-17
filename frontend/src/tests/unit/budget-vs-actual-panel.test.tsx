import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BudgetVsActualPanel } from "@/components/finance/BudgetVsActualPanel";
import type { ActiveBudgetSummary, BudgetVsActual } from "@/lib/finance-schemas";

const active: ActiveBudgetSummary = {
  id: 1,
  name: "Balanced",
  style: "balanced",
  monthly_total_gbp: 2800,
  surplus_gbp: 400,
  debt_overpayment_gbp: 150,
  buffer_target_gbp: 300,
  income_gbp: 3200,
};

describe("BudgetVsActualPanel", () => {
  it("does not treat unmatched budget lines as zero actuals", () => {
    const variance: BudgetVsActual = {
      month: "2026-08",
      plan_id: 1,
      plan_name: "Balanced",
      has_actuals: true,
      available: true,
      reason: "",
      budgeted_total_gbp: 700,
      actual_total_gbp: 359.47,
      variance_total_gbp: 340.53,
      lines: [
        {
          scope: "personal",
          category: "Household bills",
          budget_gbp: 700,
          actual_gbp: null,
          variance_gbp: null,
          percent_used: null,
          missing_actual: true,
          actual_source: "",
          transaction_count: 0,
        },
      ],
      unbudgeted_actuals: [
        {
          scope: "personal",
          category: "tesla",
          budget_gbp: 0,
          actual_gbp: 359.47,
          variance_gbp: null,
          percent_used: null,
          missing_actual: false,
          actual_source: "transactions",
          transaction_count: 1,
        },
      ],
    };

    render(<BudgetVsActualPanel variance={variance} activeBudget={active} />);
    expect(screen.getByText("Missing")).toBeInTheDocument();
    expect(screen.getByText("Allocation total")).toBeInTheDocument();
    expect(screen.getByText(/do not match a budget category/i)).toBeInTheDocument();
    expect(screen.getByText("tesla")).toBeInTheDocument();
    expect(screen.queryByText("£0.00")).not.toBeInTheDocument();
  });
});
