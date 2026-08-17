import { describe, expect, it } from "vitest";

import { accountUsesCreditLimit, debtUsesCreditLimit } from "@/lib/finance-form";

describe("revolving credit helpers", () => {
  it("keeps credit-limit fields on credit cards and Capital on Tap accounts", () => {
    expect(accountUsesCreditLimit("credit_card")).toBe(true);
    expect(accountUsesCreditLimit("capital_on_tap")).toBe(true);
    expect(accountUsesCreditLimit("current")).toBe(false);
    expect(accountUsesCreditLimit("directors_loan")).toBe(false);
  });

  it("maps Capital on Tap liabilities to the business-loan credit-limit field", () => {
    expect(debtUsesCreditLimit("credit_card")).toBe(true);
    expect(debtUsesCreditLimit("business_loan")).toBe(true);
    expect(debtUsesCreditLimit("mortgage")).toBe(false);
    expect(debtUsesCreditLimit("directors_loan")).toBe(false);
  });
});
