import { describe, expect, it } from "vitest";

import {
  debtGapLabels,
  displayOriginalBalanceGbp,
  groupDebts,
} from "@/lib/finance-debt-groups";
import type { FinanceLiability } from "@/lib/finance-schemas";

function debt(partial: Partial<FinanceLiability> & Pick<FinanceLiability, "id" | "name" | "debt_type" | "scope">): FinanceLiability {
  return {
    balance_gbp: 100,
    interest_rate_pct: 0,
    minimum_payment_gbp: 10,
    overpayment_gbp: 0,
    notes: "",
    is_active: true,
    interest_rate_known: true,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...partial,
  } as FinanceLiability;
}

describe("finance-debt-groups", () => {
  it("groups personal and business stacks with mortgage labelled", () => {
    const groups = groupDebts([
      debt({ id: 1, name: "MBNA", scope: "personal", debt_type: "credit_card" }),
      debt({ id: 2, name: "House", scope: "personal", debt_type: "mortgage" }),
      debt({ id: 3, name: "CoT", scope: "business", debt_type: "credit_card" }),
      debt({ id: 4, name: "FC", scope: "business", debt_type: "business_loan" }),
    ]);
    expect(groups.map((g) => g.key)).toEqual([
      "personal_credit_cards",
      "house_mortgage",
      "business_credit_cards",
      "business_loans",
    ]);
  });

  it("never presents the stale £175k mortgage original", () => {
    const value = displayOriginalBalanceGbp(
      debt({
        id: 1,
        name: "House",
        scope: "personal",
        debt_type: "mortgage",
        original_balance_gbp: 175000,
      }),
    );
    expect(value).toBe(82210.5);
  });

  it("surfaces APR unknown and missing limits in the list", () => {
    expect(
      debtGapLabels(
        debt({
          id: 1,
          name: "MBNA",
          scope: "personal",
          debt_type: "credit_card",
          interest_rate_known: false,
          credit_limit_gbp: null,
        }),
      ),
    ).toEqual(["APR unknown", "Credit limit missing"]);
  });
});
