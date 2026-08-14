import { describe, expect, it } from "vitest";

import { isSandboxFinanceAccount } from "@/components/finance/finance-item-utils";

describe("isSandboxFinanceAccount", () => {
  it("excludes Mock ASPSP by name or provider", () => {
    expect(
      isSandboxFinanceAccount({
        name: "Mock ASPSP",
        provider: "Mock ASPSP",
        source: "open_banking",
      }),
    ).toBe(true);
  });

  it("excludes open-banking sandbox providers", () => {
    expect(
      isSandboxFinanceAccount({
        name: "Current",
        provider: "Enable Banking sandbox",
        source: "open_banking",
      }),
    ).toBe(true);
  });

  it("keeps live Lunch Flow accounts", () => {
    expect(
      isSandboxFinanceAccount({
        name: "Lloyds Personal Current",
        provider: "Lloyds Personal",
        source: "lunch_flow",
      }),
    ).toBe(false);
  });
});
