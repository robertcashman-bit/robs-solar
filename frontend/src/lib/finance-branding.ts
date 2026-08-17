/** Display names for the two ledgers this app tracks. */

export const PERSONAL_NAME = "Robert";
export const PERSONAL_LEDGER = "Personal";
export const COMPANY_NAME = "Defence Legal Services Ltd";
export const COMPANY_SHORT = "DLS Ltd";

export function scopeLabel(scope: string): string {
  return scope === "business" ? COMPANY_SHORT : PERSONAL_LEDGER;
}

export function monthlyFlowHint(source: string | undefined): string {
  switch (source) {
    case "snapshot":
      return "From the latest personal snapshot";
    case "open_banking":
      return "From Open Banking (last 30 days)";
    case "cashflow":
      return "From confirmed cash-flow entries";
    case "budget":
      return "From the active budget plan — not imported transactions";
    default:
      return "Save a personal snapshot, or sync Open Banking";
  }
}
