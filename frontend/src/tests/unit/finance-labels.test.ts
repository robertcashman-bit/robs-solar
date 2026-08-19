import { describe, expect, it } from "vitest";

import {
  formatDataQualityIssue,
  formatInsightMeta,
  formatReconFlagLabel,
  formatSafeSpendStatus,
  formatUkDate,
  formatUkDateTime,
} from "@/lib/finance-labels";
import { isoToUkDate, ukDateToIso } from "@/components/shared/UkDateInput";

describe("finance-labels", () => {
  it("humanises reconciliation codes", () => {
    expect(formatReconFlagLabel("opening_balance_unknown", "insufficient_data")).toBe(
      "Opening balance unknown (insufficient history)",
    );
  });

  it("humanises data-quality issue codes", () => {
    expect(formatDataQualityIssue("possible_personal_on_business")).toBe(
      "Looks personal on a business account",
    );
  });

  it("humanises insight severity and category codes", () => {
    expect(formatInsightMeta("warning", "cashflow")).toBe("Warning · Cashflow");
    expect(formatInsightMeta("critical", "debt")).toBe("Critical · Debt");
  });

  it("humanises safe-to-spend status codes", () => {
    expect(formatSafeSpendStatus("HEALTHY")).toBe("Healthy");
    expect(formatSafeSpendStatus("PROJECTED_SHORTFALL")).toBe("Projected shortfall");
    expect(formatSafeSpendStatus("BUDGET_PLAN_ONLY")).toBe("Budget plan only");
  });

  it("formats ISO date-only strings as UK dd/mm/yyyy", () => {
    expect(formatUkDate("2026-08-19")).toBe("19/08/2026");
    expect(formatUkDate("2025-08-01")).toBe("01/08/2025");
  });

  it("formats Lunch Flow sync stamps like QuickFile", () => {
    const formatted = formatUkDateTime("2026-08-19T11:28:46.284269+00:00");
    expect(formatted).toMatch(/19\/08\/2026/);
    expect(formatted).not.toMatch(/T11:28/);
  });
});

describe("UkDateInput parsing", () => {
  it("round-trips ISO and UK display formats", () => {
    expect(isoToUkDate("2026-08-19")).toBe("19/08/2026");
    expect(ukDateToIso("19/08/2026")).toBe("2026-08-19");
    expect(ukDateToIso("2026-08-19")).toBe("2026-08-19");
    expect(ukDateToIso("31/02/2026")).toBeNull();
  });
});
