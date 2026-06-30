import { describe, expect, it } from "vitest";

import {
  formatCompareDelta,
  formatSavings,
  SAVINGS_EXPLAINER,
} from "@/lib/money";

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
