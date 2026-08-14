import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BudgetVsActualPanel } from "@/components/finance/BudgetVsActualPanel";
import type { ActiveBudgetSummary, BudgetVariance } from "@/lib/finance-schemas";

const active = {
  id: 1,
  name: "Live walkthrough Balanced",
  strategy: "balanced",
  period: "monthly",
  income_gbp: 7529.59,
  allocated_gbp: 8057.09,
  surplus_gbp: -527.5,
  debt_overpayment_gbp: 850.94,
  has_missing_inputs: true,
  is_deficit: true,
  income_complete: true,
  incomplete_reason: "",
} as ActiveBudgetSummary;

describe("BudgetVsActualPanel", () => {
  it("does not treat unmatched budget lines as zero actuals", () => {
    const variance: BudgetVariance = {
      available: true,
      reason: "",
      month: "2026-08",
      view: "consolidated",
      lines: [
        {
          category: "Household bills",
          kind: "essential",
          scope: "personal",
          budgeted_gbp: 700,
          actual_gbp: null,
          variance_gbp: null,
          is_missing: false,
          matched: false,
        },
      ],
      unbudgeted_actuals: [
        {
          category: "tesla",
          kind: "other",
          scope: "personal",
          budgeted_gbp: null,
          actual_gbp: 359.47,
          variance_gbp: null,
          is_missing: true,
          matched: true,
        },
      ],
      budgeted_total_gbp: 700,
      actual_total_gbp: 359.47,
    };

    render(<BudgetVsActualPanel variance={variance} activeBudget={active} />);
    expect(screen.getByText("No matching transactions")).toBeInTheDocument();
    expect(screen.getByText("Allocation total")).toBeInTheDocument();
    expect(screen.getByText(/do not match a budget category/i)).toBeInTheDocument();
    expect(screen.getByText("tesla")).toBeInTheDocument();
  });
});
