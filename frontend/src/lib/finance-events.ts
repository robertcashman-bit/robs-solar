export const FINANCE_CHANGED_EVENT = "robs-finance-changed";
export const FINANCE_OVERVIEW_READY_EVENT = "robs-finance-overview-ready";

export function notifyFinanceChanged(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new Event(FINANCE_CHANGED_EVENT));
}

export function notifyFinanceOverviewReady(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new Event(FINANCE_OVERVIEW_READY_EVENT));
}
