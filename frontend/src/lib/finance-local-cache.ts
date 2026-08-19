export const FINANCE_LAST_OVERVIEW_KEY = "robs-finance-last-overview";
export const FINANCE_LAST_TRANSACTIONS_KEY = "robs-finance-last-transactions";
export const FINANCE_LIVE_REFRESH_AT_KEY = "robs-finance-live-refresh-at";
export const FINANCE_LAST_SESSION_USER_KEY = "robs-finance-last-session-user";

/** Bumped on clear so in-flight fetches cannot rewrite caches after logout. */
let writeEpoch = 0;

export function financeCacheWriteEpoch(): number {
  return writeEpoch;
}

export function isFinanceCacheWriteCurrent(epoch: number): boolean {
  return epoch === writeEpoch;
}

/** Drop last-known figures so a later login never paints another session's numbers. */
export function clearFinanceLocalCaches(): void {
  writeEpoch += 1;
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(FINANCE_LAST_OVERVIEW_KEY);
    window.localStorage.removeItem(FINANCE_LAST_TRANSACTIONS_KEY);
    window.localStorage.removeItem(FINANCE_LAST_SESSION_USER_KEY);
    window.sessionStorage.removeItem(FINANCE_LIVE_REFRESH_AT_KEY);
    window.sessionStorage.removeItem(FINANCE_LAST_SESSION_USER_KEY);
    window.sessionStorage.removeItem("robs-finance-last-active-budgets");
  } catch {
    // ignore private mode
  }
}
