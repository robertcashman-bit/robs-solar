import { beforeEach, describe, expect, it } from "vitest";

import {
  FINANCE_LAST_OVERVIEW_KEY,
  FINANCE_LAST_TRANSACTIONS_KEY,
  FINANCE_LIVE_REFRESH_AT_KEY,
  clearFinanceLocalCaches,
} from "@/lib/finance-local-cache";

describe("clearFinanceLocalCaches", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("removes last-known overview and transactions figures", () => {
    window.localStorage.setItem(FINANCE_LAST_OVERVIEW_KEY, "{}");
    window.localStorage.setItem(FINANCE_LAST_TRANSACTIONS_KEY, "{}");
    window.sessionStorage.setItem(FINANCE_LIVE_REFRESH_AT_KEY, "1");
    clearFinanceLocalCaches();
    expect(window.localStorage.getItem(FINANCE_LAST_OVERVIEW_KEY)).toBeNull();
    expect(window.localStorage.getItem(FINANCE_LAST_TRANSACTIONS_KEY)).toBeNull();
    expect(window.sessionStorage.getItem(FINANCE_LIVE_REFRESH_AT_KEY)).toBeNull();
  });
});
