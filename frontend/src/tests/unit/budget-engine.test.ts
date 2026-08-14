import { describe, expect, it } from "vitest";

import {
  calculateBudgetTotals,
  calculateMandatoryCommitments,
  parseBudgetAmount,
  toMonthlyAmount,
  type BudgetItemLike,
} from "@/lib/budget-engine";

function item(partial: Partial<BudgetItemLike> & Pick<BudgetItemLike, "key" | "kind">): BudgetItemLike {
  return {
    scope: "personal",
    amount_gbp: 0,
    is_missing: false,
    is_transfer: false,
    ...partial,
  };
}

describe("budget engine", () => {
  it("converts supported frequencies to monthly", () => {
    expect(toMonthlyAmount(1200, "annual")).toBe(100);
    expect(toMonthlyAmount(100, "monthly")).toBe(100);
    expect(toMonthlyAmount(50, "weekly")).toBeCloseTo((50 * 52) / 12, 2);
  });

  it("treats blank amounts as missing, not zero", () => {
    expect(parseBudgetAmount("")).toBeNull();
    expect(parseBudgetAmount("  ")).toBeNull();
    expect(parseBudgetAmount("0")).toBe(0);
    expect(parseBudgetAmount("£1,234.56")).toBe(1234.56);
  });

  it("totals income, allocations, surplus and deficit", () => {
    const items = [
      item({ key: "i", kind: "income", amount_gbp: 4000 }),
      item({ key: "e", kind: "essential", amount_gbp: 1200 }),
      item({ key: "d", kind: "debt_minimum", amount_gbp: 50 }),
      item({ key: "o", kind: "debt_overpayment", amount_gbp: 150 }),
      item({ key: "b", kind: "buffer", amount_gbp: 200 }),
      item({ key: "x", kind: "discretionary", amount_gbp: 400 }),
    ];
    const totals = calculateBudgetTotals(items);
    expect(totals.income_gbp).toBe(4000);
    expect(totals.allocated_gbp).toBe(2000);
    expect(totals.surplus_gbp).toBe(2000);
    expect(totals.is_deficit).toBe(false);
    expect(calculateMandatoryCommitments(items)).toBe(1250);
  });

  it("shows a deficit when allocations exceed income", () => {
    const totals = calculateBudgetTotals([
      item({ key: "i", kind: "income", amount_gbp: 500 }),
      item({ key: "e", kind: "essential", amount_gbp: 800 }),
    ]);
    expect(totals.surplus_gbp).toBe(-300);
    expect(totals.is_deficit).toBe(true);
  });

  it("does not treat missing income as zero", () => {
    const totals = calculateBudgetTotals([
      item({ key: "i", kind: "income", amount_gbp: null, is_missing: true }),
      item({ key: "e", kind: "essential", amount_gbp: 800 }),
    ]);
    expect(totals.surplus_gbp).toBeNull();
    expect(totals.income_complete).toBe(false);
    expect(totals.has_missing_inputs).toBe(true);
  });

  it("excludes transfers from the consolidated view", () => {
    const items = [
      item({ key: "pi", kind: "income", amount_gbp: 3000 }),
      item({ key: "bi", kind: "income", scope: "business", amount_gbp: 8000 }),
      item({
        key: "sal",
        kind: "essential",
        scope: "business",
        amount_gbp: 3000,
        is_transfer: true,
      }),
      item({ key: "be", kind: "essential", scope: "business", amount_gbp: 2000 }),
    ];
    expect(calculateBudgetTotals(items, "personal").income_gbp).toBe(3000);
    expect(calculateBudgetTotals(items, "business").essential_gbp).toBe(5000);
    expect(calculateBudgetTotals(items, "consolidated").essential_gbp).toBe(2000);
    expect(calculateBudgetTotals(items, "consolidated").income_gbp).toBe(11000);
  });
});
