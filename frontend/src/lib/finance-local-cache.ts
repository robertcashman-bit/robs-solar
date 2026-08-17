export const FINANCE_LAST_OVERVIEW_KEY = "robs-finance-last-overview";
export const FINANCE_LAST_TRANSACTIONS_KEY = "robs-finance-last-transactions";
export const FINANCE_LIVE_REFRESH_AT_KEY = "robs-finance-live-refresh-at";

/** Drop last-known figures so a later login never paints another session's numbers. */
export function clearFinanceLocalCaches(): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(FINANCE_LAST_OVERVIEW_KEY);
    window.localStorage.removeItem(FINANCE_LAST_TRANSACTIONS_KEY);
    window.sessionStorage.removeItem(FINANCE_LIVE_REFRESH_AT_KEY);
  } catch {
    // ignore private mode
  }
}
