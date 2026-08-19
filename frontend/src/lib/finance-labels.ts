/** Human-readable labels for internal finance codes shown in the UI. */

const RECON_KIND_LABELS: Record<string, string> = {
  opening_balance_unknown: "Opening balance unknown",
  opening_balance_mismatch: "Opening balance mismatch",
  ledger_mismatch: "Ledger mismatch",
  balance_mismatch: "Balance mismatch",
};

const RECON_STATUS_LABELS: Record<string, string> = {
  insufficient_data: "insufficient history",
  unresolved: "unresolved",
  confirmed: "confirmed",
  ignored: "ignored",
};

const DATA_QUALITY_ISSUE_LABELS: Record<string, string> = {
  possible_personal_on_business: "Looks personal on a business account",
  possible_business_on_personal: "Looks business on a personal account",
  missing_category: "Missing category",
  missing_date: "Missing date",
  duplicate_suspect: "Possible duplicate",
};

const INSIGHT_SEVERITY_LABELS: Record<string, string> = {
  info: "Info",
  warning: "Warning",
  critical: "Critical",
};

const INSIGHT_CATEGORY_LABELS: Record<string, string> = {
  cashflow: "Cashflow",
  debt: "Debt",
  tax: "Tax",
  business: "Business",
  energy: "Energy",
};

const SAFE_SPEND_STATUS_LABELS: Record<string, string> = {
  HEALTHY: "Healthy",
  CAUTION: "Caution — below buffer",
  LOW_CASH: "Low cash",
  PROJECTED_SHORTFALL: "Projected shortfall",
  BUDGET_PLAN_ONLY: "Budget plan only",
};

export function formatReconFlagLabel(kind: string, status: string): string {
  const kindLabel = RECON_KIND_LABELS[kind] ?? kind.replaceAll("_", " ");
  const statusLabel = RECON_STATUS_LABELS[status] ?? status.replaceAll("_", " ");
  return `${kindLabel} (${statusLabel})`;
}

export function formatDataQualityIssue(issue: string): string {
  return DATA_QUALITY_ISSUE_LABELS[issue] ?? issue.replaceAll("_", " ");
}

export function formatInsightMeta(severity: string, category: string): string {
  const severityLabel = INSIGHT_SEVERITY_LABELS[severity] ?? severity.replaceAll("_", " ");
  const categoryLabel = INSIGHT_CATEGORY_LABELS[category] ?? category.replaceAll("_", " ");
  return `${severityLabel} · ${categoryLabel}`;
}

export function formatSafeSpendStatus(status: string | null | undefined): string {
  if (!status) return "";
  return SAFE_SPEND_STATUS_LABELS[status] ?? status.replaceAll("_", " ");
}

/** Format an ISO date-only string (yyyy-mm-dd) as UK dd/mm/yyyy. */
export function formatUkDate(value: string | null | undefined): string {
  if (value == null || value === "") return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value.trim());
  if (match) {
    return `${match[3]}/${match[2]}/${match[1]}`;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("en-GB");
}

/** Format an ISO / Date for UK display, matching QuickFile sync stamps. */
export function formatUkDateTime(value: string | Date | null | undefined): string {
  if (value == null || value === "") return "";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("en-GB");
}
