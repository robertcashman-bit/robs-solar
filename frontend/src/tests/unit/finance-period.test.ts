import { afterEach, describe, expect, it } from "vitest";

import {
  FINANCE_PERIOD_STORAGE_KEY,
  overviewDefaultPeriod,
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
    expect(parseFinancePeriod("24m")).toBe("24m");
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

  it("builds last-year as rolling 12 months through today", () => {
    const range = periodDateRange("12m", new Date(Date.UTC(2026, 7, 21)));
    expect(range.dateFrom).toBe("2025-08-21");
    expect(range.dateTo).toBe("2026-08-21");
    expect(range.monthsRequested).toBe(12);
  });

  it("builds 2-years as rolling 24 months through today", () => {
    const range = periodDateRange("24m", new Date(Date.UTC(2026, 7, 21)));
    expect(range.dateFrom).toBe("2024-08-21");
    expect(range.dateTo).toBe("2026-08-21");
    expect(range.monthsRequested).toBe(24);
  });

  it("preserves day-of-month across rolling year boundary", () => {
    const range = periodDateRange("12m", new Date(Date.UTC(2026, 2, 10)));
    expect(range.dateFrom).toBe("2025-03-10");
    expect(range.dateTo).toBe("2026-03-10");
  });

  it("clamps rolling start day when the target month is shorter", () => {
    // Feb 29 2024 → Feb 2023 (non-leap) clamps to 28.
    const range = periodDateRange("12m", new Date(Date.UTC(2024, 1, 29)));
    expect(range.dateFrom).toBe("2023-02-28");
    expect(range.dateTo).toBe("2024-02-29");
  });

  it("labels periods for UI chips", () => {
    expect(periodLabel("mtd")).toBe("This month to date");
    expect(periodLabel("1m")).toBe("Last month");
    expect(periodLabel("12m")).toBe("Last year");
    expect(periodLabel("24m")).toBe("2 years");
  });

  it("defaults Overview to last month on day 1 and mtd afterwards", () => {
    expect(overviewDefaultPeriod(new Date(2026, 8, 1))).toBe("1m");
    expect(overviewDefaultPeriod(new Date(2026, 8, 2))).toBe("mtd");
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
