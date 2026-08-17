/** Display names for the two ledgers this app tracks. */

export const PERSONAL_NAME = "Robert";
export const PERSONAL_LEDGER = "Personal";
export const COMPANY_NAME = "Defence Legal Services Ltd";
export const COMPANY_SHORT = "DLS Ltd";

export function scopeLabel(scope: string): string {
  return scope === "business" ? COMPANY_SHORT : PERSONAL_LEDGER;
}

/** Label for monthly income/spend source — actual vs plan vs none. */
export function monthlyFlowHint(source: string | undefined): string {
  switch (source) {
    case "snapshot":
      return "From the latest personal snapshot";
    case "open_banking":
      return "From live Open Banking sync (last 30 days)";
    case "cashflow":
      return "From confirmed cash-flow entries";
    case "budget":
      return "Budget plan estimate — not live income or spending";
    case "transactions":
      return "From imported personal transactions (transfers excluded)";
    default:
      return "No live sync, snapshot, or budget plan for this month";
  }
}

/** Short badge for Safe to Spend / tile chips. */
export function monthlyFlowBadge(source: string | undefined): string {
  switch (source) {
    case "snapshot":
      return "Snapshot";
    case "open_banking":
      return "Live sync";
    case "cashflow":
      return "Cash-flow";
    case "budget":
      return "Budget plan";
    case "transactions":
      return "Imported";
    default:
      return "No data";
  }
}
