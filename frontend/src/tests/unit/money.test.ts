import { describe, expect, it } from "vitest";

import { formatGbp, isCurrentMonthSnapshot, parseRequiredAmount } from "@/lib/money";

describe("parseRequiredAmount", () => {
  it("rejects empty and non-numeric input instead of coercing to zero", () => {
    expect(parseRequiredAmount("")).toBeNull();
    expect(parseRequiredAmount("   ")).toBeNull();
    expect(parseRequiredAmount("abc")).toBeNull();
  });

  it("parses valid amounts including zero", () => {
    expect(parseRequiredAmount("0")).toBe(0);
    expect(parseRequiredAmount("12.50")).toBe(12.5);
  });
});

describe("isCurrentMonthSnapshot", () => {
  it("matches month-only and first-of-month dates", () => {
    expect(isCurrentMonthSnapshot("2026-08", "2026-08")).toBe(true);
    expect(isCurrentMonthSnapshot("2026-08-01", "2026-08")).toBe(true);
    expect(isCurrentMonthSnapshot("2026-07-31", "2026-08")).toBe(false);
  });
});

describe("formatGbp", () => {
  it("shows an em dash for missing values", () => {
    expect(formatGbp(null)).toBe("—");
    expect(formatGbp(undefined)).toBe("—");
  });
});
