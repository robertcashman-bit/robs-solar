import { describe, expect, it } from "vitest";

import {
  formatDataQualityIssue,
  formatReconFlagLabel,
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
