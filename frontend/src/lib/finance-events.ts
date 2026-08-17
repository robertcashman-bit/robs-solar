export const FINANCE_CHANGED_EVENT = "robs-finance-changed";

export function notifyFinanceChanged(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new Event(FINANCE_CHANGED_EVENT));
}
