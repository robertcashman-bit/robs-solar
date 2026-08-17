import { describe, expect, it } from "vitest";

import { monthlyFlowBadge, monthlyFlowHint } from "@/lib/finance-branding";

describe("monthlyFlowHint", () => {
  it("distinguishes live sources from budget plans", () => {
    expect(monthlyFlowHint("snapshot")).toMatch(/snapshot/i);
    expect(monthlyFlowHint("open_banking")).toMatch(/live Open Banking/i);
    expect(monthlyFlowHint("cashflow")).toMatch(/cash-flow/i);
    expect(monthlyFlowHint("budget")).toMatch(/Budget plan estimate/i);
    expect(monthlyFlowHint("budget")).toMatch(/not live/i);
    expect(monthlyFlowHint("transactions")).toMatch(/transfers excluded/i);
    expect(monthlyFlowHint("none")).toMatch(/No live sync/i);
    expect(monthlyFlowHint(undefined)).toMatch(/No live sync/i);
  });

  it("exposes short badges for tiles", () => {
    expect(monthlyFlowBadge("budget")).toBe("Budget plan");
    expect(monthlyFlowBadge("open_banking")).toBe("Live sync");
    expect(monthlyFlowBadge("snapshot")).toBe("Snapshot");
  });
});
