import { describe, expect, it } from "vitest";

import {
  formatAccountingGbp,
  formatCompareDelta,
  formatFinanceGbp,
  formatQuickFilePeriod,
  formatSavings,
  SAVINGS_EXPLAINER,
} from "@/lib/money";

describe("formatFinanceGbp", () => {
  it("prefixes assets with plus", () => {
    expect(formatFinanceGbp(100, "asset").text).toBe("+£100.00");
    expect(formatFinanceGbp(100, "asset").tone).toBe("positive");
  });

  it("prefixes debts with minus", () => {
    expect(formatFinanceGbp(50, "debt").text).toBe("−£50.00");
    expect(formatFinanceGbp(50, "debt").tone).toBe("negative");
  });

  it("uses signed role for surplus/deficit", () => {
    expect(formatFinanceGbp(-25, "signed").text).toBe("−£25.00");
    expect(formatFinanceGbp(25, "signed").text).toBe("+£25.00");
  });
});

describe("formatSavings", () => {
  it("shows saved wording for positive savings", () => {
    const result = formatSavings(1.37, "GBP");
    expect(result.headline).toBe("£1.37 saved");
    expect(result.tone).toBe("positive");
  });

  it("shows more-than-no-solar wording for negative savings", () => {
    const result = formatSavings(-1.37, "GBP");
    expect(result.headline).toBe("£1.37 more than no-solar");
    expect(result.tone).toBe("negative");
    expect(result.amount).toBe("£1.37");
  });
});

describe("formatCompareDelta", () => {
  it("labels improvement vs previous period", () => {
    const result = formatCompareDelta(-1.37, -2.71, "GBP", true, "yesterday");
    expect(result.text).toBe("+£1.34 vs yesterday");
    expect(result.tone).toBe("up");
  });
});

describe("SAVINGS_EXPLAINER", () => {
  it("mentions import-heavy windows", () => {
    expect(SAVINGS_EXPLAINER).toMatch(/import-heavy/i);
  });
});

describe("formatAccountingGbp", () => {
  it("formats positive amounts without sign colours", () => {
    expect(formatAccountingGbp(1234.5)).toBe("£1,234.50");
  });

  it("wraps negative amounts in parentheses", () => {
    expect(formatAccountingGbp(-50)).toBe("(£50.00)");
  });
});

describe("formatQuickFilePeriod", () => {
  it("uses UK date format", () => {
    expect(formatQuickFilePeriod("2026-01-01", "2026-07-02")).toBe("01/01/2026 to 02/07/2026");
  });
});
