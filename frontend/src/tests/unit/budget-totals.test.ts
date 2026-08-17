import { describe, expect, it } from "vitest";

import { summariseBudgetLines } from "@/lib/budget-totals";
import { parseGbp, parseMoneyInput } from "@/lib/money";

describe("summariseBudgetLines", () => {
  it("recalculates surplus when a category changes", () => {
    const before = summariseBudgetLines(
      [
        { category: "Household / mortgage contribution", amount_gbp: 900 },
        { category: "Personal spending", amount_gbp: 400 },
      ],
      2000,
    );
    const after = summariseBudgetLines(
      [
        { category: "Household / mortgage contribution", amount_gbp: 1000 },
        { category: "Personal spending", amount_gbp: 400 },
      ],
      2000,
    );
    expect(before.surplus_gbp).toBe(700);
    expect(after.surplus_gbp).toBe(600);
    expect(after.discretionary_gbp).toBe(400);
  });
});

describe("parseGbp", () => {
  it("accepts pasted sterling values", () => {
    expect(parseGbp("£1,250.50")).toBe(1250.5);
    expect(parseGbp("  80 ")).toBe(80);
  });

  it("does not coerce blank or invalid text to zero", () => {
    expect(Number.isNaN(parseGbp(""))).toBe(true);
    expect(Number.isNaN(parseGbp("abc"))).toBe(true);
    expect(parseMoneyInput("")).toBeNull();
    expect(parseMoneyInput("not-a-number")).toBeNull();
    expect(parseMoneyInput("£1,234.56")).toBe(1234.56);
  });
});
