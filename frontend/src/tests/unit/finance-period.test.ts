import { afterEach, describe, expect, it } from "vitest";

import {
  FINANCE_PERIOD_STORAGE_KEY,
  parseFinancePeriod,
  parseFinanceScope,
  periodDateRange,
  periodLabel,
  readStoredPeriodPrefs,
  writeStoredPeriodPrefs,
} from "@/lib/finance-period";

describe("finance-period", () => {
  afterEach(() => {
    window.localStorage.removeItem(FINANCE_PERIOD_STORAGE_KEY);
  });

  it("parses known period keys and falls back", () => {
    expect(parseFinancePeriod("3m")).toBe("3m");
    expect(parseFinancePeriod("mtd")).toBe("mtd");
    expect(parseFinancePeriod("nope")).toBe("1m");
  });

  it("parses scope keys", () => {
    expect(parseFinanceScope("business")).toBe("business");
    expect(parseFinanceScope("x")).toBe("personal");
  });

  it("builds inclusive calendar lookback ending last month", () => {
    const range = periodDateRange("3m", new Date(Date.UTC(2026, 7, 18)));
    expect(range.dateFrom).toBe("2026-05-01");
    expect(range.dateTo).toBe("2026-07-31");
    expect(range.monthsRequested).toBe(3);
  });

  it("builds month-to-date window through today", () => {
    const range = periodDateRange("mtd", new Date(Date.UTC(2026, 7, 18)));
    expect(range.dateFrom).toBe("2026-08-01");
    expect(range.dateTo).toBe("2026-08-18");
    expect(range.monthsRequested).toBe(1);
  });

  it("labels periods for UI chips", () => {
    expect(periodLabel("mtd")).toBe("This month to date");
    expect(periodLabel("1m")).toBe("Last month");
    expect(periodLabel("12m")).toBe("Last year");
  });

  it("persists preferences in localStorage including legacy keys", () => {
    writeStoredPeriodPrefs({
      period: "6m",
      personalPeriod: "6m",
      businessPeriod: "3m",
      scope: "both",
    });
    expect(readStoredPeriodPrefs()).toEqual({
      period: "6m",
      personalPeriod: "6m",
      businessPeriod: "3m",
      scope: "both",
    });
    writeStoredPeriodPrefs({
      period: "mtd",
      personalPeriod: "mtd",
      businessPeriod: "1m",
      scope: "personal",
    });
    expect(readStoredPeriodPrefs()?.period).toBe("mtd");
  });
});
