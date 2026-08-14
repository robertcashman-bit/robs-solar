import { describe, expect, it } from "vitest";

import { parseRequiredNumber } from "@/lib/money";

describe("parseRequiredNumber", () => {
  it("parses plain and currency-formatted amounts", () => {
    expect(parseRequiredNumber("12.5", "Amount")).toBe(12.5);
    expect(parseRequiredNumber("£1,234.56", "Amount")).toBe(1234.56);
  });

  it("rejects blank and invalid values instead of coercing to zero", () => {
    expect(() => parseRequiredNumber("", "Amount")).toThrow(/not saved as zero/i);
    expect(() => parseRequiredNumber("abc", "Amount")).toThrow(/not saved as zero/i);
  });
});
